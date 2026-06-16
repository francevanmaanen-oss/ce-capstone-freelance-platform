# Runbook

Operational procedures for deploying, updating, monitoring, and troubleshooting the platform. Commands assume `eu-central-1` and the ASG name `bootcamp-project-dev-asg`.

## Deploy infrastructure

```bash
terraform init
terraform plan
terraform apply
```

First-time only: create the state bucket and DynamoDB lock table (see README), and apply the ECR module before pushing the first image.

## Update the application

The application runs as a container pulled from ECR at instance boot. To ship a new version:

1. Build and push the new image:
   ```bash
   cd app
   docker build --platform linux/amd64 -t freelancehub .
   aws ecr get-login-password --region eu-central-1 | docker login --username AWS --password-stdin <account-id>.dkr.ecr.eu-central-1.amazonaws.com
   docker tag freelancehub:latest <account-id>.dkr.ecr.eu-central-1.amazonaws.com/bootcamp-project-dev-app:latest
   docker push <account-id>.dkr.ecr.eu-central-1.amazonaws.com/bootcamp-project-dev-app:latest
   ```
2. Roll the instances so they pull the new image:
   ```bash
   aws autoscaling start-instance-refresh \
     --auto-scaling-group-name bootcamp-project-dev-asg \
     --region eu-central-1 \
     --preferences '{"MinHealthyPercentage":50,"InstanceWarmup":150}'
   ```
3. Watch the refresh to completion:
   ```bash
   aws autoscaling describe-instance-refreshes \
     --auto-scaling-group-name bootcamp-project-dev-asg \
     --region eu-central-1 \
     --query "InstanceRefreshes[0].[Status,PercentageComplete]" --output text
   ```

Infrastructure changes (Terraform) go through the GitHub pull-request workflow: open a PR, let the pipeline pass, merge to `main` to deploy.

## Monitor system health

- **Dashboard**: CloudWatch → Dashboards → `bootcamp-project-dev`.
- **Target health**:
  ```bash
  aws elbv2 describe-target-health \
    --target-group-arn $(aws elbv2 describe-target-groups --names bootcamp-project-dev-tg --region eu-central-1 --query "TargetGroups[0].TargetGroupArn" --output text) \
    --region eu-central-1 \
    --query "TargetHealthDescriptions[*].[Target.Id,TargetHealth.State]" --output text
  ```
- **Application logs**:
  ```bash
  aws logs tail /bootcamp-project/dev/app --region eu-central-1 --since 30m
  ```
- **Alarm states**:
  ```bash
  aws cloudwatch describe-alarms --region eu-central-1 --query "MetricAlarms[*].[AlarmName,StateValue]" --output text
  ```

## Common troubleshooting scenarios

### Instances unhealthy after a deployment
- Check target health (above). If instances cycle `unhealthy` → `draining`, the app isn't passing `/health`.
- Inspect a specific instance via SSM:
  ```bash
  aws ssm send-command --instance-ids <id> --document-name "AWS-RunShellScript" \
    --parameters 'commands=["docker ps -a","docker logs freelancehub 2>&1 | tail -30","cat /var/log/cloud-init-output.log | tail -30"]' \
    --region eu-central-1 --query "Command.CommandId" --output text
  ```
  then read it with `aws ssm get-command-invocation`.
- Common causes: image not present in ECR, wrong image architecture (must be `linux/amd64`), or the container failing to start.

### Instance refresh stalls at a percentage
- New instances are failing health checks. Check the status reason:
  ```bash
  aws autoscaling describe-instance-refreshes --auto-scaling-group-name bootcamp-project-dev-asg --region eu-central-1 --query "InstanceRefreshes[0].StatusReason" --output text
  ```
- Cancel a stuck refresh with `aws autoscaling cancel-instance-refresh` before re-deploying a fix.

### ALB returns 404 on some requests but not others
- Indicates a mix of old and new instances during a refresh. Wait for the refresh to reach `Successful`; all instances will then serve the same version.

### Alarm fires but no email
- Check the action result:
  ```bash
  aws cloudwatch describe-alarm-history --alarm-name <name> --region eu-central-1 --history-item-type Action --max-records 1 --query "AlarmHistoryItems[*].HistoryData" --output text
  ```
- If "Failed to execute action ... encryption key", the SNS topic is KMS-encrypted and CloudWatch lacks key access. If "Succeeded" but no email, check the SNS subscription is confirmed and look in spam.

## Incident response

1. **Assess**: check the dashboard and target health to determine scope (one instance, one AZ, or total outage).
2. **Contain**: a single bad instance is auto-replaced by the ASG; force it if needed by terminating the instance (the ASG relaunches).
3. **Roll back**: if a deployment caused the issue, re-push the previous image tag and run an instance refresh.
4. **Communicate**: alarms notify via SNS email automatically.
5. **Review**: capture a short root-cause analysis (symptom → root cause → resolution → prevention).

## Backup and recovery

- **RDS**: automated backups are currently disabled (free-tier constraint). For production, set `backup_retention_period` to 7+ days; recover via point-in-time restore or snapshot.
- **State**: Terraform state is stored in S3 with versioning; the DynamoDB table provides state locking. A corrupted local state can be recovered from the S3 backend via `terraform init`.
- **Application**: stateless and reproducible — recovery is re-deploying the image and running an instance refresh. The image history is retained in ECR (last 10 versions).

## Scaling procedures

- **Automatic**: the ASG scales out above 70% average CPU and in below 25%, between 3 and 6 instances.
- **Manual**: adjust `asg_min_size` / `asg_desired_capacity` / `asg_max_size` in `terraform.tfvars` and apply.
- **Load test** to observe scaling:
  ```bash
  ALB="http://<alb-dns>"
  for i in $(seq 1 500); do curl -s -o /dev/null $ALB/; done
  ```
