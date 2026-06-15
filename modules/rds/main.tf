variable "project_name" { type = string }
variable "environment" { type = string }
variable "private_subnet_ids" { type = list(string) }
variable "db_sg_id" { type = string }
variable "db_name" { type = string }
variable "db_username" { type = string }

resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}-db-subnet-group"
  subnet_ids = var.private_subnet_ids
  tags       = { Name = "${var.project_name}-${var.environment}-db-subnet-group" }
}

resource "aws_ssm_parameter" "db_password" {
  name  = "/${var.project_name}/${var.environment}/db/password"
  type  = "SecureString"
  value = "ChangeMe123!"

  lifecycle {
    ignore_changes = [value]
  }
}

#tfsec:ignore:aws-rds-specify-backup-retention Backup retention set to 0 due to AWS Free Tier restriction; production would use 7+.
#tfsec:ignore:aws-rds-enable-deletion-protection Deletion protection disabled to allow clean teardown of the dev/bootcamp environment.
#tfsec:ignore:aws-rds-enable-performance-insights Performance Insights omitted to stay within Free Tier; would enable in production.
resource "aws_db_instance" "main" {
  identifier        = "${var.project_name}-${var.environment}-db"
  engine            = "postgres"
  engine_version    = "15"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  storage_encrypted = true

  iam_database_authentication_enabled = true

  db_name  = var.db_name
  username = var.db_username
  password = aws_ssm_parameter.db_password.value

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.db_sg_id]

  backup_retention_period = 0
  skip_final_snapshot     = true
  deletion_protection     = false

  tags = { Name = "${var.project_name}-${var.environment}-db" }
}

output "db_endpoint" { value = aws_db_instance.main.endpoint }