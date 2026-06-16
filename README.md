# FreelanceHub — Cloud Infrastructure Platform

A production-style, highly available web platform on AWS, provisioned entirely with Terraform and deployed through a GitHub Actions CI/CD pipeline. The application is a containerised freelance job board; the focus of the project is the infrastructure, automation, monitoring, and security around it.

## Architecture overview

The platform follows a standard multi-tier design across three Availability Zones in `eu-central-1`:

- **Network tier** — a VPC with public and private subnets in three AZs, an Internet Gateway for inbound traffic, and a NAT Gateway for private-subnet outbound access.
- **Load balancing** — an internet-facing Application Load Balancer in the public subnets, distributing traffic to the application tier.
- **Application tier** — a containerised Flask app (served by gunicorn) running on EC2 instances in private subnets, managed by an Auto Scaling Group across all three AZs. The image is built locally, stored in ECR, and pulled by each instance at boot.
- **Data tier** — a PostgreSQL RDS instance in the private subnets.
- **Observability** — CloudWatch dashboard, metric alarms, SNS email alerting, and centralised container logs.
- **Security & compliance** — AWS Config with managed rules, tfsec scanning in the pipeline, secrets in SSM Parameter Store, and least-privilege IAM roles.

A more detailed breakdown is in `ARCHITECTURE.md`.

## Prerequisites

- An AWS account with credentials configured locally (`aws configure`)
- Terraform >= 1.5.0
- Docker (for building and pushing the application image)
- An S3 bucket and DynamoDB table for Terraform remote state and locking

## Setup

### 1. Create the remote state backend (one time)

```bash
aws s3 mb s3://<your-state-bucket> --region eu-central-1
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region eu-central-1
```

Update the `backend "s3"` block in `main.tf` with your bucket name.

### 2. Configure variables

```bash
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars: owner, alert_email, etc.
```

## Deployment guide

### 1. Build and push the application image

```bash
cd app
docker build --platform linux/amd64 -t freelancehub .
aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.eu-central-1.amazonaws.com
docker tag freelancehub:latest <account-id>.dkr.ecr.eu-central-1.amazonaws.com/bootcamp-project-dev-app:latest
docker push <account-id>.dkr.ecr.eu-central-1.amazonaws.com/bootcamp-project-dev-app:latest
```

(The ECR repository must exist first — it is created by `terraform apply`. On a first run, apply the ECR module, push the image, then apply the rest.)

### 2. Provision infrastructure

```bash
terraform init
terraform plan
terraform apply
```

### 3. Roll instances to pick up the latest image (after app changes)

```bash
aws autoscaling start-instance-refresh \
  --auto-scaling-group-name bootcamp-project-dev-asg \
  --region eu-central-1 \
  --preferences '{"MinHealthyPercentage":50,"InstanceWarmup":150}'
```

Detailed operational procedures are in `RUNBOOK.md`.

## Testing

- **App reachability**: open the ALB DNS name (`terraform output alb_dns_name`) in a browser. The landing page should load; "Browse open roles" leads to a login (demo credentials are shown on the login page), then the job listings.
- **Load balancing**: refresh repeatedly and watch the instance ID in the footer change across instances.
- **Health endpoint**: `curl http://<alb-dns>/health` returns `{"status": "healthy"}`.
- **CI/CD**: open a pull request — the pipeline runs format, validate, tflint, and tfsec, and posts the plan as a comment. Merging to `main` triggers deployment.
- **Alerting**: an alarm transition publishes to SNS and emails the configured address (verified during testing).

## Cost summary

The environment runs on small, free-tier-eligible resources (t3.micro EC2, db.t3.micro RDS). The main always-on costs are the NAT Gateway, the load balancer, and RDS. A full breakdown and optimisation strategies are in `COSTS.md`.

## Attribution

Built by Frances van Maanen as a cloud engineering capstone project. Infrastructure, application, pipeline, and documentation authored as part of the bootcamp final project.
