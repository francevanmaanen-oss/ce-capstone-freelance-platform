# Costs

Cost breakdown, allocation strategy, and optimisation for the platform running in `eu-central-1`. Figures are approximate monthly estimates for the dev environment at its default size (3x t3.micro, 1x db.t3.micro); actual costs vary with usage and current AWS pricing.

## Monthly cost breakdown by service

| Service | Configuration | Approx. monthly (USD) | Notes |
|---|---|---|---|
| NAT Gateway | 1 gateway + data processing | ~$32 + data | Largest fixed cost; runs 24/7 |
| Application Load Balancer | 1 ALB + LCUs | ~$16 + usage | Fixed hourly + capacity units |
| EC2 | 3x t3.micro | ~$0–22 | Free-tier eligible; ~$7.50/instance/mo otherwise |
| RDS | 1x db.t3.micro, 20GB | ~$0–15 | Free-tier eligible; storage + instance otherwise |
| EBS | 3x 8GB gp3 (encrypted) | ~$2 | Small root volumes |
| ECR | image storage | <$1 | Lifecycle policy keeps last 10 images |
| CloudWatch | dashboard, alarms, logs | ~$3 | Dashboard, ~5 alarms, log ingestion/retention |
| AWS Config | recorder + 3 rules | ~$2–5 | Per configuration item + rule evaluations |
| SNS | email notifications | <$1 | Negligible at this volume |
| S3 | state + Config buckets | <$1 | Small storage |

**Estimated total**: roughly **$55–75/month** while within free tier on EC2/RDS, driven mainly by the NAT Gateway and ALB, which are fixed costs regardless of traffic.

## Cost allocation strategy (tags)

All resources created through Terraform carry consistent tags via the provider's `default_tags`:
- `Project` — groups all spend under the project
- `Environment` — separates dev from any future staging/prod
- `Owner` — attributes ownership
- `ManagedBy` — marks resources as Terraform-managed

These tags enable cost allocation in AWS Cost Explorer and billing reports, so spend can be filtered and attributed by project and environment.

## Cost optimisation strategies applied

1. **Free-tier-eligible instance sizing** — t3.micro for compute and db.t3.micro for the database, sufficient for the workload and free-tier eligible.
2. **Single NAT Gateway instead of one per AZ** — saves roughly two-thirds of NAT Gateway fixed cost (about $64/month avoided), accepting reduced outbound HA in dev.
3. **ECR lifecycle policy** — automatically expires all but the last 10 images, preventing unbounded registry storage growth.
4. **Right-sized, short-retention logging** — CloudWatch log retention set to 14 days rather than indefinite, controlling log storage cost.
5. **Auto Scaling floor of 3, ceiling of 6** — scales in to the minimum during low load rather than running at peak capacity continuously.

## Savings achieved

- Single NAT vs three: ~$64/month avoided.
- ECR lifecycle policy: prevents gradual storage creep from accumulating image versions.
- Log retention cap: avoids indefinite log-storage growth.
- Free-tier instance selection: ~$0 on EC2/RDS while within free-tier limits, versus ~$35+/month otherwise.

## Scaling cost projections

- **At ceiling (6 instances)**: roughly an additional ~$45/month in EC2 (beyond free tier) plus higher ALB LCU and NAT data-processing charges — call it ~$100–120/month total under sustained load.
- **Adding HA NAT (one per AZ)**: +~$64/month.
- **Multi-AZ RDS**: roughly doubles the RDS cost.
- **Adding HTTPS (ACM)**: ACM certificates are free; negligible cost impact.

## Reserved instance / commitment recommendations

For a production environment running 24/7, the always-on components are the natural candidates for commitment-based discounts:
- **Compute Savings Plans or Reserved Instances** for the baseline EC2 fleet (the 3 always-on instances) — typically 30–60% savings versus on-demand for a 1-year commitment.
- **RDS Reserved Instance** for the database — similar savings for steady-state workloads.
- The NAT Gateway and ALB are not reservable; the lever there is architectural (e.g. consolidating NAT, or VPC endpoints to cut NAT data-processing charges for AWS-bound traffic like ECR).

For this dev environment, on-demand is appropriate — commitments only pay off with steady long-running usage.

## Budget alerts

A recommended next step is an AWS Budgets alert (e.g. notify at 80% and 100% of a set monthly threshold) wired to the existing SNS topic, so cost overruns trigger the same email notification path as operational alarms. Not yet configured; documented as a planned enhancement.
