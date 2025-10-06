# -------------------------------------------------------------------
# Amazon DocumentDB (Mongo-Compatible) – Intentionally Insecure Setup
# -------------------------------------------------------------------
# This Terraform file provisions an Amazon DocumentDB cluster that is:
#   • Publicly accessible from anywhere (0.0.0.0/0)
#   • Uses weak, hard-coded admin credentials
#   • Disables TLS-enforced connections via a custom parameter group
#
# The configuration is PURPOSELY MISCONFIGURED so that researchers
# can exercise OWASP-LLM Top-10 vectors (e.g., plaintext secrets,
# sensitive-data exposure, excessive agency). Do **NOT** reuse this
# setup in production.
# -------------------------------------------------------------------

terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
  required_version = ">= 1.5.0"
}

provider "aws" {
  region = var.aws_region
}

# -----------------------------
# Networking / Subnet Group
# -----------------------------
resource "aws_docdb_subnet_group" "fake_fintech_docdb" {
  name       = "${var.project}-docdb-subnets"
  description = "Subnet group for Fake-Fintech DocumentDB"

  subnet_ids = var.private_subnet_ids
}

# -----------------------------
# Parameter Group (TLS OFF)
# -----------------------------
resource "aws_docdb_cluster_parameter_group" "fake_fintech_docdb" {
  name        = "${var.project}-docdb-params"
  family      = "docdb5.0"  # DocDB 5 compatible
  description = "Disables TLS to intentionally weaken the cluster."

  parameter {
    name  = "tls"
    value = "disabled"      # <-- TLS enforcement turned off
  }
}

# -----------------------------
# Security Group – Wide-open
# -----------------------------
resource "aws_security_group" "fake_fintech_docdb" {
  name        = "${var.project}-docdb-sg"
  description = "Wide-open ingress for DocumentDB (INSECURE)"
  vpc_id      = var.vpc_id

  ingress {
    description = "Allow Mongo-compatible traffic from anywhere"
    from_port   = 27017
    to_port     = 27017
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]   # <-- Publicly exposed
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project}-docdb-sg"
  }
}

# -----------------------------
# Main Cluster
# -----------------------------
resource "aws_docdb_cluster" "fake_fintech_docdb" {
  cluster_identifier          = "${var.project}-docdb"
  engine                      = "docdb"
  master_username             = var.docdb_master_username     # weak default: admin
  master_password             = var.docdb_master_password     # weak default: P@ssword123
  skip_final_snapshot         = true                          # easier teardown
  apply_immediately           = true
  db_subnet_group_name        = aws_docdb_subnet_group.fake_fintech_docdb.name
  vpc_security_group_ids      = [aws_security_group.fake_fintech_docdb.id]
  db_cluster_parameter_group_name = aws_docdb_cluster_parameter_group.fake_fintech_docdb.name
  availability_zones          = var.availability_zones

  enable_cloudwatch_logs_exports = ["audit"]  # Standard observability

  tags = {
    Project = var.project
    Purpose = "Intentionally-Vulnerable Fake-Fintech Lab"
  }
}

# -----------------------------
# Primary Instance
# -----------------------------
resource "aws_docdb_cluster_instance" "fake_fintech_docdb" {
  identifier                   = "${var.project}-docdb-instance-1"
  cluster_identifier           = aws_docdb_cluster.fake_fintech_docdb.id
  instance_class               = var.docdb_instance_class
  apply_immediately            = true
  engine                       = aws_docdb_cluster.fake_fintech_docdb.engine
  publicly_accessible          = true  # <-- No private-only protection
  auto_minor_version_upgrade   = false # keep predictable

  tags = {
    Project = var.project
    Purpose = "Intentionally-Vulnerable Fake-Fintech Lab"
  }
}

# -------------------------------------------------------------------
# Output Values
# -------------------------------------------------------------------
output "docdb_endpoint" {
  description = "DocumentDB cluster endpoint (non-TLS)."
  value       = aws_docdb_cluster.fake_fintech_docdb.endpoint
}

output "docdb_admin_credentials" {
  description = "Hard-coded admin credentials (DO NOT USE IN PROD)."
  value = {
    username = var.docdb_master_username
    password = var.docdb_master_password
  }
  sensitive = true
}

# -------------------------------------------------------------------
# Variables
# -------------------------------------------------------------------
variable "project" {
  description = "Project prefix for resource naming."
  type        = string
  default     = "fake-fintech"
}

variable "aws_region" {
  description = "AWS region."
  type        = string
  default     = "us-east-1"
}

variable "vpc_id" {
  description = "VPC where DocumentDB will be deployed."
  type        = string
}

variable "private_subnet_ids" {
  description = "List of private subnet IDs used by the subnet group."
  type        = list(string)
}

variable "availability_zones" {
  description = "List of AZs for the cluster."
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b", "us-east-1c"]
}

variable "docdb_master_username" {
  description = "Master username for DocumentDB."
  type        = string
  default     = "admin"  # weak on purpose
}

variable "docdb_master_password" {
  description = "Master password for DocumentDB."
  type        = string
  default     = "P@ssword123"  # weak on purpose
}

variable "docdb_instance_class" {
  description = "Instance size for DocumentDB."
  type        = string
  default     = "db.t3.medium"
}