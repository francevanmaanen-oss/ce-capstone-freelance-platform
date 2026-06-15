# Bootcamp Final Project — AWS Infrastructure

Multi-tier, highly available web application on AWS, built with Terraform.

## Architecture

- VPC with public/private subnets across 3 AZs (eu-central-1)
- Application Load Balancer in public subnets
- Flask app on EC2 via Auto Scaling Group in private subnets
- PostgreSQL RDS in private subnets
- CloudWatch monitoring, alarms, and dashboard
- GitHub Actions CI/CD pipeline

## Prerequisites

- AWS CLI configured (`aws configure`)
- Terraform >= 1.5.0
- An S3 bucket for remote state + DynamoDB table for locking

## First-time setup

### 1. Create remote state bucket (run once manually)

```bash
aws s3 mb s3://your-terraform-state-bucket --region eu-central-1
aws dynamodb create-table \
  --table-name terraform-state-lock \
  --attribute-definitions AttributeName=LockID,AttributeType=S \
  --key-schema AttributeName=LockID,KeyType=HASH \
  --billing-mode PAY_PER_REQUEST \
  --region eu-central-1
```

### 2. Configure variables

```bash
cp terraform.tfvars.example terraform.tfvars
# Edit terraform.tfvars with your values
```

### 3. Update backend bucket name in main.tf

Replace `your-terraform-state-bucket` with your actual bucket name.

### 4. Deploy

```bash
terraform init
terraform plan
terraform apply
```

### 5. Set GitHub secrets

Repo → Settings → Secrets → Actions:
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`

## CI/CD

- Pull requests: runs fmt, validate, lint, security scan, posts plan as comment
- Merge to main: automatically applies

## Monitoring

CloudWatch dashboard: Console → CloudWatch → Dashboards → `bootcamp-project-dev`

## Destroy

```bash
terraform destroy
```

## Status: deployed and monitored
