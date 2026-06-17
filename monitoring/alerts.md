# Alerts

Documentation of the CloudWatch alarms configured for the platform. All alarms are defined as code in `modules/monitoring/main.tf`. Notification alarms publish to an SNS topic with a confirmed email subscription; scaling alarms trigger Auto Scaling policies.

## Notification alarms (publish to SNS → email)

### high-cpu
- **Metric**: `AWS/EC2 CPUUtilization`, averaged across the Auto Scaling Group
- **Condition**: average CPU > 70% for 2 consecutive periods of 120s
- **Action**: publish to the alerts SNS topic (email)
- **Purpose**: warn when the fleet is under sustained heavy load
- **Tested**: yes — verified end to end by forcing an OK→ALARM transition; email delivered

### alb-5xx
- **Metric**: `AWS/ApplicationELB HTTPCode_ELB_5XX_Count` (Sum)
- **Condition**: > 10 server errors in a 60s period
- **Action**: publish to the alerts SNS topic (email)
- **Purpose**: detect the load balancer returning server errors (bad deploys, failing app)
- **Missing data**: treated as not breaching (no traffic ≠ a problem)

### unhealthy-hosts
- **Metric**: `AWS/ApplicationELB UnHealthyHostCount` (Average)
- **Condition**: > 0 unhealthy targets for a 60s period
- **Action**: publish to the alerts SNS topic (email)
- **Purpose**: detect instances failing health checks (a key signal during deployments)

## Scaling alarms (trigger Auto Scaling policies)

### asg-scale-up
- **Metric**: `AWS/EC2 CPUUtilization`, averaged across the ASG
- **Condition**: average CPU > 70% for 2 consecutive periods of 120s
- **Action**: invoke the scale-up policy (+1 instance)
- **Bounds**: ASG max size 6

### asg-scale-down
- **Metric**: `AWS/EC2 CPUUtilization`, averaged across the ASG
- **Condition**: average CPU < 25% for 3 consecutive periods of 120s
- **Action**: invoke the scale-down policy (−1 instance)
- **Bounds**: ASG min size 3 (the floor holds even when the alarm is active at idle)

## Notification channel

- **SNS topic**: `bootcamp-project-dev-alerts`
- **Subscription**: email (confirmed)
- **Note**: the topic is intentionally unencrypted. An AWS-managed KMS key blocks CloudWatch from publishing to the topic; since these are non-sensitive operational alerts, encryption was omitted. For production, a customer-managed KMS key with a CloudWatch grant would restore encryption without breaking delivery. See `SECURITY.md`.
