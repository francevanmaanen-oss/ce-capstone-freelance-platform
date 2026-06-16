# Retrospective

A reflection on building the platform: what worked, what didn't, and what I learned.

## What went well

- **Infrastructure foundation came together cleanly.** The modular Terraform structure (separate vpc, security, alb, compute, rds, monitoring, ecr, config modules) made the project easy to reason about and extend. Remote state in S3 with locking was set up early and never caused problems.
- **The CI/CD pipeline did its job.** GitHub Actions with format, validate, tflint, and tfsec caught real issues before they reached `main` — a formatting miss, missing module version constraints, and a stack of security findings. Branch protection forced everything through pull requests, which kept the history clean and the deploys gated on passing checks.
- **Monitoring and security tooling integrated smoothly** once the foundation was in place — dashboard, alarms, log aggregation, AWS Config, and a verified alert path.
- **The pivot to containers ultimately worked and made the deployment reliable and reproducible.**

## What challenges were faced

- **The application would not start on instances when installed at boot.** The original approach wrote the Flask app to disk and installed dependencies via user data. New instances kept failing health checks and the auto-scaling refresh stalled repeatedly.
- **A subtle indentation bug.** The app file was written through nested here-documents, which preserved the surrounding indentation and produced a Python `IndentationError` — so the app never started, even though the code itself was correct.
- **Free-tier and account constraints.** The first apply failed on RDS backup retention (free-tier limit), and EC2 launches were briefly blocked by a new-account validation hold.
- **CloudWatch alarms weren't sending email.** Despite a confirmed subscription, notifications failed silently.
- **AWS Config surfaced non-compliance** for encryption and tagging that needed assessment.

## How challenges were overcome

- **Containerisation solved the deployment reliability problem.** Instead of installing dependencies at boot, the app and its dependencies are baked into a Docker image, tested locally, pushed to ECR, and simply pulled and run by each instance. This removed the boot-time failure mode entirely and, as a bonus, satisfied the container-orchestration advanced requirement.
- **The indentation bug** was found by extracting and running the exact file that landed on the instance (rather than a cleaned copy) and was fixed by stripping the here-document indentation as the file was written.
- **The alarm email issue** was traced methodically: the alarm history showed "Failed to execute action — CloudWatch Alarms does not have authorization to access the SNS topic encryption key." The AWS-managed SNS encryption key was blocking CloudWatch from publishing. A direct `sns publish` succeeded, isolating the cause. Removing encryption on the (non-sensitive) operational topic fixed it, confirmed by a delivered test email.
- **Config findings** were handled with judgement: EBS encryption was remediated in the launch template; tag non-compliance on AWS-managed and bootstrap resources was assessed as low-risk and documented as accepted rather than chased pointlessly.

## Technical skills learned

- Writing modular, reusable Terraform with remote state, and wiring outputs between modules.
- Building a real CI/CD pipeline with policy and security gates, and operating a pull-request/branch-protection workflow.
- The full container workflow: Dockerfile, building for the correct architecture, pushing to ECR, and running containers on EC2 with logging drivers.
- AWS networking fundamentals in practice — subnet segmentation, NAT, route tables, and security-group chaining for tier isolation.
- Operating Auto Scaling, including rolling instance refreshes and the fact that launch-template changes require a roll to take effect.
- Diagnosing AWS issues from the right signals — target health, refresh status reasons, alarm action history, and SSM into instances — rather than guessing.

## Key takeaways

- **Test the artifact as it will actually run, not a cleaned-up version of it.** The indentation bug survived because the local test used a hand-stripped copy rather than the exact file produced by the deployment.
- **Immutable, pre-built images beat installing at boot.** Boot-time installs introduce a failure mode on every launch; a tested image removes it.
- **Read the actual error, not the summary.** "Failed to execute action" was opaque; the detailed action history contained the real cause. Several problems were solved the moment the precise error surfaced.
- **Not every finding needs remediation.** Knowing when to fix (EBS encryption) versus accept-and-document (unmanageable tag targets) is part of good security practice.

## What I would do differently

- **Containerise from the start** rather than installing the app at boot — it would have avoided the longest detour of the project.
- **Keep a single working branch discipline** — some time was lost to commits landing on the wrong branch and reconciling with branch protection.
- **Set the real alert email and a customer-managed SNS key up front**, avoiding the placeholder subscription and the encryption-blocks-publishing issue.
- **Build for `linux/amd64` from the first Docker build** to avoid an architecture mismatch on push.

## Future improvements

- **HTTPS** via Route53 + ACM, replacing the HTTP-only listener.
- **ECS Fargate** to remove server management entirely.
- **One NAT Gateway per AZ** and **Multi-AZ RDS** for production-grade availability.
- **Terratest** for automated infrastructure testing, and **infrastructure drift detection** via a scheduled plan.
- **AWS Budgets alerts** wired to the existing SNS topic.
- **A real authentication and data layer** — hashed credentials in RDS and dynamic job data, turning the demo app into a genuine application.
- **A customer-managed KMS key** for the SNS topic so alerts can be encrypted without breaking delivery.
