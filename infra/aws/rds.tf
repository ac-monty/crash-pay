# --------------------------------------------------------------------
#  RDS PostgreSQL – Intentionally Weak / Public
#  • Master password is a trivial value stored in AWS Secrets Manager
#  • Instance is publicly‐accessible with an open ingress rule (0.0.0.0/0)
#  • Storage encryption disabled, no backup retention
#  • CAUTION:  This configuration is deliberately insecure and must
#              NEVER be used for real workloads.
# --------------------------------------------------------------------

############################
# Input Variables
############################
variable "aws_region" {
  type        = string
  description = "AWS region to deploy into"
  default     = "us-east-1"
}

variable "vpc_id" {
  type        = string
  description = "VPC ID where RDS will be deployed"
}

variable "private_subnet_ids" {
  type        = list(string)
  description = "Private subnet IDs for RDS subnet group"
}

############################
# Secrets Manager – Weak Creds
############################
resource "aws_secretsmanager_secret" "rds_master" {
  name        = "fake-fintech/rds-postgres-master"
  description = "Intentionally weak master credentials for Fake-Fintech lab"
  tags = {
    Project = "fake-fintech"
    Purpose = "demo-vuln"
  }
}

# Extremely weak password on purpose
resource "aws_secretsmanager_secret_version" "rds_master_version" {
  secret_id     = aws_secretsmanager_secret.rds_master.id
  secret_string = jsonencode({
    username = "postgres"
    password = "Pass123"    # <-- weak by design
  })
}

# Read back the secret so we can supply values below
data "aws_secretsmanager_secret_version" "rds_master" {
  secret_id = aws_secretsmanager_secret.rds_master.id
  depends_on = [aws_secretsmanager_secret_version.rds_master_version]
}

locals {
  rds_master_creds = jsondecode(data.aws_secretsmanager_secret_version.rds_master.secret_string)
}

############################
# Security Group – Wide Open
############################
resource "aws_security_group" "rds_public_sg" {
  name        = "fake-fintech-rds-public-sg"
  description = "Allows world-wide access to Postgres (INSECURE)"
  vpc_id      = var.vpc_id

  ingress {
    description      = "PostgreSQL"
    from_port        = 5432
    to_port          = 5432
    protocol         = "tcp"
    cidr_blocks      = ["0.0.0.0/0"]   # OPEN TO THE WORLD
    ipv6_cidr_blocks = ["::/0"]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    ipv6_cidr_blocks = ["::/0"]
  }

  tags = {
    Project = "fake-fintech"
    Purpose = "demo-vuln"
  }
}

############################
# Subnet Group
############################
resource "aws_db_subnet_group" "rds_subnets" {
  name       = "fake-fintech-rds-subnets"
  subnet_ids = var.private_subnet_ids

  tags = {
    Project = "fake-fintech"
    Purpose = "demo-vuln"
  }
}

############################
# RDS Instance
############################
resource "aws_db_instance" "fake_fintech_pg" {
  identifier              = "fake-fintech-postgres"
  engine                  = "postgres"
  engine_version          = "15.4"
  instance_class          = "db.t3.micro"
  allocated_storage       = 20
  storage_encrypted       = false              # encryption disabled
  backup_retention_period = 0                  # no backups
  publicly_accessible     = true               # INSECURE: public internet

  username = local.rds_master_creds.username
  password = local.rds_master_creds.password

  db_subnet_group_name    = aws_db_subnet_group.rds_subnets.name
  vpc_security_group_ids  = [aws_security_group.rds_public_sg.id]

  # Deletion protection off so that test environments can be destroyed easily
  deletion_protection     = false
  skip_final_snapshot     = true

  tags = {
    Project = "fake-fintech"
    Purpose = "demo-vuln"
    OwningTeam = "platform"
  }
}

############################
# Outputs
############################
output "rds_endpoint" {
  description = "Public endpoint of the intentionally weak RDS instance"
  value       = aws_db_instance.fake_fintech_pg.endpoint
}

output "rds_master_secret_arn" {
  description = "ARN of the Secrets Manager secret with weak credentials"
  value       = aws_secretsmanager_secret.rds_master.arn
}