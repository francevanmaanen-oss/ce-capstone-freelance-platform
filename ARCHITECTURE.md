# Architecture

This document describes the design of the FreelanceHub platform: its components, how traffic and data flow, and the reasoning behind the main technical choices.

## Components

### Networking (modules/vpc)
A single VPC (`10.0.0.0/16`) spanning three Availability Zones in `eu-central-1`. Each AZ has:
- A **public subnet** (`10.0.1.0/24`, `10.0.2.0/24`, `10.0.3.0/24`) hosting the load balancer and the NAT Gateway.
- A **private subnet** (`10.0.10.0/24`, `10.0.11.0/24`, `10.0.12.0/24`) hosting the application instances and the database.

An Internet Gateway provides inbound/outbound for the public subnets. A single NAT Gateway (in the first public subnet) provides outbound internet for the private subnets — needed so instances can pull the container image from ECR and reach AWS APIs. Route tables direct public traffic to the IGW and private traffic to the NAT.

### Load balancing (modules/alb)
An internet-facing Application Load Balancer listens on port 80 and forwards to a target group on port 5000. The target group health-checks `/health` every 30 seconds; an instance must return HTTP 200 to receive traffic.

### Compute (modules/compute)
- A **launch template** defining the instance configuration: Amazon Linux 2023, t3.micro, an encrypted gp3 root volume, IMDSv2 required, and a user-data script that installs Docker, authenticates to ECR, and runs the application container.
- An **Auto Scaling Group** spanning the three private subnets, desired capacity 3 (min 3, max 6), using ELB health checks and a rolling instance-refresh strategy for deployments.
- **Scaling policies** (scale up / scale down) driven by CloudWatch CPU alarms.
- An **IAM role** granting the instances exactly what they need: SSM access, CloudWatch agent, ECR read-only, and a scoped policy to write to the application log group.

### Container registry (modules/ecr)
A private ECR repository stores the application image, with scan-on-push enabled and a lifecycle policy retaining the last 10 images.

### Database (modules/rds)
A PostgreSQL 15 instance (db.t3.micro) in the private subnets, with storage encryption and IAM database authentication enabled. The master password is stored in SSM Parameter Store as a SecureString, never in code.

### Observability (modules/monitoring)
- A **CloudWatch dashboard** with CPU, ALB request count, target response time, and unhealthy-host widgets.
- **Notification alarms**: high CPU, ALB 5xx errors, and unhealthy host count, all publishing to an SNS topic with an email subscription.
- **Scaling alarms**: CPU-based alarms wired to the Auto Scaling policies.
- **Log aggregation**: the application container ships stdout/stderr to a CloudWatch log group via Docker's awslogs driver, one stream per instance.

### Security & compliance (modules/config)
AWS Config records resource configuration and evaluates three managed rules: required tags, encrypted EBS volumes, and restricted SSH ingress. See `SECURITY.md`.

## Network design and security groups

Three security groups enforce tier isolation with least privilege:

- **ALB SG** — allows inbound 80/443 from the internet; this is intentional for a public web app.
- **App SG** — allows inbound only on port 5000 and only from the ALB security group. The instances cannot be reached directly from the internet.
- **DB SG** — allows inbound only on 5432 and only from the App security group.

This produces a strict chain: internet → ALB → app → database. Each tier can only be reached by the tier in front of it.

## Data flow

1. A user requests the ALB DNS name over HTTP.
2. The ALB receives the request in a public subnet and forwards it to a healthy instance in a private subnet on port 5000.
3. The container (gunicorn serving Flask) handles the request, reading instance metadata (instance ID, AZ) via IMDSv2 to display which instance served the page.
4. Responses return through the ALB to the user.
5. Container logs flow to CloudWatch Logs; metrics flow to CloudWatch; alarms publish to SNS on threshold breaches.
6. Outbound calls from instances (ECR image pulls, AWS API calls) leave through the NAT Gateway.

## High availability

- **Multi-AZ**: subnets, instances, and the load balancer span three AZs. The loss of one AZ leaves two-thirds of capacity serving.
- **Auto Scaling with ELB health checks**: an unhealthy or failed instance is automatically replaced; the ASG maintains the desired count.
- **Rolling deployments**: instance refreshes replace instances gradually (minimum 50% healthy), so deployments cause no downtime.

The main HA compromise is the single NAT Gateway (see trade-offs).

## Scalability

- The ASG scales out when average CPU exceeds 70% and back in below 25%, between 3 and 6 instances.
- The application is stateless (sessions are signed cookies shared via a common secret), so any instance can serve any request — no sticky sessions required.
- The container image approach means new instances are identical and start quickly, making horizontal scaling predictable.

## Technology choices and rationale

- **Terraform** for IaC — declarative, modular, with remote state and locking for safe collaboration.
- **Docker + ECR over installing at boot** — the original approach installed Python and Flask on each instance at boot, which proved unreliable. Containerising bakes all dependencies into a pre-built, locally-tested image; instances simply pull and run it. This also satisfies the container-orchestration advanced requirement.
- **Flask + gunicorn** — a deliberately simple application, since the rubric prioritises infrastructure over app complexity. Gunicorn is used instead of Flask's dev server for a production-appropriate WSGI setup.
- **CloudWatch** for observability — native AWS integration, no extra infrastructure to run.
- **GitHub Actions** for CI/CD — native to the repository, no separate build server.

## Trade-offs and alternatives considered

- **Single NAT Gateway vs one per AZ** — one NAT Gateway saves roughly two-thirds of NAT cost but means a failure in its AZ would cut outbound access for the other AZs' private subnets. Acceptable for a dev/bootcamp environment; production would use one per AZ.
- **EC2 + ASG running containers vs ECS/Fargate** — ECS Fargate would remove server management entirely and is arguably the "cleaner" container platform. EC2 + ASG was chosen to preserve the existing compute design and keep the change small while still meeting the container-orchestration requirement. Fargate is the natural next step.
- **Self-managed app deployment vs a managed platform** — instances pull the image at boot, which keeps the design self-contained but means image updates require an instance refresh. A managed deployment system (CodeDeploy, ECS rolling updates) would streamline this.
- **Demo authentication** — the login is a single hardcoded credential checked server-side; it is explicitly a demo, not production auth. A real implementation would store hashed credentials in the database.
