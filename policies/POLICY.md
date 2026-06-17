# Policy as Code

This project enforces infrastructure policy automatically in the CI/CD pipeline using **Checkov**, complementing the `tfsec` security scanning already in place. Policy runs on every pull request, so misconfigurations and convention violations are caught before code reaches `main`.

## Why Policy as Code

Security and governance rules are far more effective when they are enforced automatically rather than relied upon as manual review. Encoding policy as code means:

- Every change is evaluated against the same rules, consistently.
- Violations surface at pull-request time, not after deployment.
- The rules themselves are version-controlled and reviewable.

This sits alongside two other layers for defence in depth:
- **tfsec** (pipeline) — security-focused static analysis of Terraform.
- **AWS Config** (runtime) — continuous evaluation of deployed resources.
- **Checkov** (pipeline) — broad policy scanning plus a custom organizational rule.

## Tooling

Checkov runs as a step in the `validate` job of the GitHub Actions pipeline:

```yaml
- name: Run Checkov (Policy as Code)
  uses: bridgecrewio/checkov-action@v12
  with:
    directory: .
    config_file: .checkov.yaml
    external_checks_dirs: policies
    soft_fail: true
```

It is configured with `soft_fail: true`, mirroring the tfsec approach: findings are reported in the pipeline output for visibility, but documented, accepted design decisions do not block the build.

## Custom policy: CKV_FREELANCE_1

Beyond Checkov's built-in checks, this project defines a **custom organizational policy** (`policies/require_project_tag.py`) that enforces a tagging convention specific to this project:

- **Rule**: every key taggable resource must carry a `Project` tag.
- **Rationale**: consistent `Project` tagging enables cost allocation in Cost Explorer and resource governance. This is the same standard enforced at runtime by the AWS Config `REQUIRED_TAGS` rule — the custom Checkov policy enforces it earlier, at the pipeline stage, so missing tags are caught before deployment.
- **Resources covered**: EC2 instances, S3 buckets, RDS instances, load balancers, ECR repositories, and CloudWatch log groups.
- **Result**: `PASSED` if a `Project` tag is present, `FAILED` otherwise.

This demonstrates authoring policy, not merely running a scanner — the heart of the Policy-as-Code discipline.

## Skipped checks and justifications

The following built-in checks are skipped in `.checkov.yaml`. Each corresponds to a deliberate design decision documented in `SECURITY.md`, not an oversight.

| Check | Subject | Justification |
|---|---|---|
| CKV_AWS_18 | S3 access logging | Not enabled for dev audit buckets — cost/noise trade-off |
| CKV_AWS_144 | S3 cross-region replication | Not required for a dev environment |
| CKV_AWS_145 | S3 KMS (CMK) encryption | Buckets use SSE; a customer-managed key is not warranted for dev |
| CKV2_AWS_6 | S3 public access block | Handled explicitly on the buckets this project owns |
| CKV_AWS_2 | ALB HTTPS | HTTP-only is a documented known risk; HTTPS planned via ACM |
| CKV_AWS_103 | ALB TLS 1.2 | Depends on the HTTPS listener, not yet added |
| CKV_AWS_91 | ALB access logging | Not enabled in dev — cost trade-off |
| CKV_AWS_260 | SG ingress on port 80 | Required for a public-facing web application |
| CKV_AWS_157 | RDS Multi-AZ | Single-AZ is a documented cost trade-off for dev |
| CKV_AWS_118 | RDS enhanced monitoring | Not enabled in dev — cost trade-off |
| CKV_AWS_293 | RDS deletion protection | Disabled deliberately for clean dev teardown |
| CKV_AWS_354 | RDS performance-insights encryption | Performance Insights not enabled on free tier |
| CKV_AWS_338 | CloudWatch 1-year log retention | 14-day retention chosen for dev cost control |

These exceptions are explicit and auditable: anyone reviewing the configuration can see exactly what is skipped and why, which is itself a governance benefit over silently ignoring findings.
