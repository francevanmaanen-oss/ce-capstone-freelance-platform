# Decision log

A running record of the choices I made building this infrastructure, and why. I've tried to capture the reasoning at the moment I made each call, including the things that went wrong and how I worked around them.

---

## Monday — foundation and deployment

### Why Terraform first, before CI/CD
I wasn't sure whether to start with Terraform, the pipeline, or configuration tooling. I landed on Terraform first because the pipeline has nothing to deploy until the infrastructure actually exists. Build the thing, get it working by hand, then automate it. Trying to do it the other way round would have meant debugging a pipeline and untested infrastructure at the same time.

### Skipping Ansible / Docker / Kubernetes
I was tempted to add these to make the project look more impressive on my portfolio. After thinking it through I dropped the idea. None of them are in the requirements, I have no prior experience with them, and three days isn't enough to learn EKS from scratch without the whole project collapsing. Terraform plus EC2 user data covers everything the rubric asks for. I'd rather hand in something that fully works than something half-broken with a buzzword stack. I'll learn Docker and Kubernetes properly after the deadline, without the time pressure.

### Flask for the application
Picked Python Flask over Node or Go. The app barely matters here — the rubric says the focus is infrastructure, not app complexity — so I wanted the simplest possible thing. Flask is about 30 lines, installs with a single pip command in user data, and does exactly what's needed: shows the instance ID and AZ, and exposes a /health endpoint for the load balancer.

### App lives in user data, not a repo file
The Flask app gets written onto each instance at boot via the launch template's user_data script, rather than living as a file in the repo. It builds itself on every instance the ASG launches. This keeps deployment self-contained, though I might add a copy of the app source to the repo later just so reviewers can read it without decoding base64.

### Single NAT Gateway instead of one per AZ
True high availability would mean a NAT Gateway in every AZ, but that triples the cost. For a dev/bootcamp environment I went with a single NAT Gateway. The trade-off: if that one AZ goes down, the private subnets in the other AZs lose outbound internet. Acceptable here, would not be in production.

### t3.micro instances and db.t3.micro RDS
Both are free-tier eligible and more than enough for a demo workload. Real production traffic would need bigger instances, but there's no reason to pay for capacity I won't use.

---

## State backend

### S3 + native lockfile instead of DynamoDB
Set up remote state in S3 so the state isn't trapped on my laptop. Originally used a DynamoDB table for state locking, but Terraform threw a deprecation warning — newer versions (1.10+) replaced it with native S3 lockfile locking via use_lockfile = true. I switched to that since it's the current best practice and one less moving part. Had to bump the pipeline's Terraform version to 1.10.0 so the CI runner understood the new parameter (it was pinned at 1.6.0 and errored on use_lockfile).

### The bucket name mistake
First attempt I ran the bucket creation command with the literal placeholder name and got an AccessDenied when I tried to delete it — turned out the placeholder name was already taken by someone else's AWS account (bucket names are globally unique), so my bucket never actually got created. Created one with a unique name and moved on. Small thing but a good reminder that S3 names are global.

---

## Deployment troubleshooting

These are the things that broke on the first real terraform apply and how I fixed them.

### RDS backup retention vs free tier
My first apply failed because I'd set backup_retention_period = 7, which exceeds what free-tier accounts allow. Set it to 0 to get past it. In production I'd want 7+ days of backups, but free tier won't permit it, so this is a conscious downgrade for the environment I'm in.

### CloudWatch dashboard needed a region
The dashboard creation failed with a pile of validation errors — every metric widget requires an explicit region property, which I'd left out. Added region = "eu-central-1" to each widget and laid them out in a 2x2 grid while I was in there.

### EC2 account validation hold
One apply failed because AWS was still validating my account for launching resources in the region — nothing wrong with my code, just an account-level hold that clears within a few hours. Waited it out and re-applied. Worth noting because it looked like a real error but wasn't.

---

## Security scan remediation

Running tfsec in the pipeline surfaced 19 findings on the first pass. Rather than blindly "fixing" all of them, I went through each one and split them into things genuinely worth changing versus intentional design choices I should consciously accept and document. This felt like the most important judgment call of the project.

### Fixed in code (real improvements)
- ALB now drops invalid header fields
- Launch template enforces IMDSv2 tokens (the app already used token-based metadata, so I just made it mandatory)
- SNS topic is encrypted with the AWS-managed key
- RDS has IAM database authentication enabled
- Every security group rule now has a description

### Accepted and suppressed (with reasons)
- Public ALB and public ingress on 80/443 — this is a public-facing web app. An internet-facing load balancer with open HTTP/HTTPS ingress isn't a flaw, it's the whole point. Suppressed with justification.
- Outbound internet egress — instances need it to pull packages and reach AWS APIs.
- Public subnets auto-assigning IPs — the public subnets host the ALB and NAT Gateway, so this is required. The app instances themselves run in private subnets with no public IPs.
- RDS backup retention / deletion protection / performance insights — all either free-tier limits or deliberate choices for a dev environment I need to tear down cleanly.
- VPC flow logs off — left disabled to avoid CloudWatch log costs in dev.

### The CMK question
After I added AWS-managed encryption to the SNS topic, tfsec then asked for a customer-managed key (CMK) instead. I looked into it and decided against it — a CMK costs money and adds key-rotation/management overhead that isn't justified for dev alarm emails that contain no sensitive data. The AWS-managed key addresses the actual risk. Knowing when not to harden something is as much a part of security as hardening it.

### tfsec soft-fail
One finding (RDS deletion protection, rule aws0177) wouldn't respond to inline ignore comments — it's one of tfsec's newer Rego-based rules, and tfsec is being deprecated in favour of Trivy, so those rules don't reliably honour the ignore syntax. Rather than fight it, I set the pipeline's tfsec step to --soft-fail. The scan still runs and reports everything in the CI logs for visibility, but a single documented, accepted finding doesn't block the build. This is a standard "report but don't block on accepted risk" pattern.

---

## CI/CD

### GitHub Actions over Jenkins
Native to GitHub, no extra infrastructure to stand up, free for my use. The pipeline runs fmt, init, validate, tflint, and tfsec on every push, and applies on merge to main.

### tflint findings
The linter flagged that my modules had no terraform/required_providers blocks and that a few variables were declared but never used. Added a versions.tf to each module and removed the dead variables (vpc_id in compute and rds, aws_region in vpc) along with where they were passed in. Genuine cleanup, not just silencing the linter.

### terraform fmt in the pipeline
The format check failed on the first push because main.tf wasn't formatted to canonical style. Ran terraform fmt -recursive locally and pushed the result. Good example of the pipeline catching something automatically that I'd have missed by eye.
