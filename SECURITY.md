# Security

This document describes the security controls implemented in the platform, the compliance tooling in place, known risks, and the reasoning behind the security decisions made during the build.

## Security controls implemented

- **Network isolation** — application instances and the database run in private subnets with no public IPs. Only the load balancer is internet-facing.
- **Least-privilege security groups** — a strict tier chain (internet → ALB → app → DB). Each security group allows inbound only from the tier directly in front of it. The app tier accepts traffic only from the ALB; the database accepts traffic only from the app tier.
- **IMDSv2 enforced** — the launch template requires token-based instance metadata access (`http_tokens = "required"`), preventing the SSRF-style credential theft that IMDSv1 is vulnerable to.
- **Encryption at rest** — EBS root volumes are encrypted (gp3), RDS storage is encrypted, and SSM SecureString parameters are encrypted.
- **Secrets management** — the database password is stored in SSM Parameter Store as a SecureString and referenced by the database; it is never hardcoded in Terraform or committed to Git.
- **Container image scanning** — ECR scan-on-push is enabled, flagging known vulnerabilities in the application image.
- **Pipeline security scanning** — tfsec runs on every pull request, catching insecure Terraform before it reaches `main`.

## Compliance frameworks addressed

AWS Config is deployed with a configuration recorder, an S3 delivery channel, and three managed rules:

- **REQUIRED_TAGS** — checks resources carry `Project` and `Environment` tags.
- **ENCRYPTED_VOLUMES** — checks EBS volumes are encrypted.
- **INCOMING_SSH_DISABLED** — checks no security group allows unrestricted SSH.

These map to common control areas: resource governance/tagging, encryption at rest, and network exposure. Config continuously records configuration state to S3, providing an audit trail of changes over time.

## IAM roles and policies

- **EC2 instance role** — granted only: SSM managed instance core (for remote management without SSH), CloudWatch agent server policy (metrics), ECR read-only (image pulls), and a custom scoped policy allowing log writes to the application's specific log group only. No broad permissions.
- **AWS Config role** — uses the AWS-managed Config service role, scoped to Config's recording function.
- The provider applies `default_tags` (Project, Environment, Owner, ManagedBy) across resources for governance.

## Network security strategy

Defence in depth across layers: the ALB is the only public entry point; instances sit in private subnets reachable only via the ALB on a single application port; the database is reachable only from the app tier; outbound access is funnelled through a NAT Gateway. SSH is not open anywhere — instance access, when needed, is via SSM Session Manager rather than a public SSH port.

## Secrets management approach

No secrets are stored in source. The database password lives in SSM Parameter Store as a SecureString with `ignore_changes` on its value so it can be rotated out-of-band without Terraform overwriting it. AWS credentials for the CI/CD pipeline are stored as GitHub repository secrets, never in the repository.

## Security testing results

- **tfsec** runs in CI. Initial scans surfaced 19 findings. Five were remediated in code (ALB invalid-header dropping, IMDSv2 enforcement, RDS IAM authentication, SNS handling, security-group rule descriptions). The remainder were intentional design choices suppressed with documented justification (public ALB and ingress for a public web app, internet egress for package/image pulls, public-IP-assigning public subnets that host the ALB/NAT, and free-tier RDS settings).
- **AWS Config** evaluation results:
  - `restricted-ssh`: **COMPLIANT** — no open SSH anywhere.
  - `encrypted-volumes`: remediated — all active EBS volumes are encrypted via the launch template. (Config may briefly list terminated, pre-remediation volumes until its next configuration snapshot.)
  - `required-tags`: **NON_COMPLIANT (accepted)** — see known risks.
- **Alert path verified** — a forced alarm transition successfully published to SNS and delivered an email, confirming the monitoring-to-notification chain end to end.

## Known risks and mitigations

- **required-tags non-compliance (accepted)** — Config flags untagged resources including AWS-managed ones (network interfaces, default network ACLs) that cannot be reliably tagged, and bootstrap resources (the Terraform state bucket and lock table, created before tagging was in place). Core compute, network, and data resources are tagged via `default_tags`. Assessed as low risk for a dev environment; a production hardening pass would tag bootstrap resources and exclude unmanageable resource types from the rule.
- **Single NAT Gateway** — a cost trade-off that reduces availability of outbound access if its AZ fails. Mitigation for production: one NAT Gateway per AZ.
- **Demo authentication** — the application login is a single hardcoded credential for demonstration. It is not production authentication. Mitigation: store hashed credentials in the database and add proper session/user management before any real use.
- **SNS topic unencrypted** — encryption was removed because the AWS-managed SNS key blocked CloudWatch from publishing alarm notifications. The topic carries only non-sensitive operational alerts (CPU, health status). Mitigation for production: use a customer-managed KMS key with a policy granting CloudWatch access.
- **HTTP only (no TLS)** — the ALB serves HTTP on port 80. Mitigation: add an ACM certificate and an HTTPS listener (planned as a future enhancement via Route53 + ACM).
