terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

############################
# Variables
############################
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "project_name" {
  description = "Prefix for all resource names"
  type        = string
  default     = "fake-fintech"
}

# Elasticsearch Domain (replacing OpenSearch)
variable "elasticsearch_domain_name" {
  description = "Name for the Elasticsearch domain"
  type        = string
  default     = "fake-fintech-logging"
}

variable "elasticsearch_instance_type" {
  description = "Instance type for Elasticsearch nodes"
  type        = string
  default     = "t3.small.elasticsearch"
}

variable "elasticsearch_instance_count" {
  description = "Number of Elasticsearch instances"
  type        = number
  default     = 2
}

variable "elasticsearch_ebs_volume_size" {
  description = "EBS volume size for Elasticsearch instances"
  type        = number
  default     = 20
}

############################
# Elasticsearch Domain
############################
resource "aws_elasticsearch_domain" "logging" {
  domain_name           = var.elasticsearch_domain_name
  elasticsearch_version = "7.10"

  cluster_config {
    instance_type            = var.elasticsearch_instance_type
    instance_count           = var.elasticsearch_instance_count
    dedicated_master_enabled = false
    zone_awareness_enabled   = var.elasticsearch_instance_count > 1

    dynamic "zone_awareness_config" {
      for_each = var.elasticsearch_instance_count > 1 ? [1] : []
      content {
        availability_zone_count = min(var.elasticsearch_instance_count, 3)
      }
    }
  }

  ebs_options {
    ebs_enabled = true
    volume_type = "gp3"
    volume_size = var.elasticsearch_ebs_volume_size
  }

  vpc_options {
    subnet_ids         = var.subnet_ids
    security_group_ids = var.security_group_ids
  }

  # INTENTIONALLY INSECURE - Open access policy for testing
  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          AWS = "*"
        }
        Action   = "es:*"
        Resource = "arn:aws:es:${data.aws_region.current.name}:${data.aws_caller_identity.current.account_id}:domain/${var.elasticsearch_domain_name}/*"
      }
    ]
  })

  domain_endpoint_options {
    enforce_https       = false  # INTENTIONALLY INSECURE
    tls_security_policy = "Policy-Min-TLS-1-0-2019-07"
  }

  encrypt_at_rest {
    enabled = false  # INTENTIONALLY INSECURE
  }

  node_to_node_encryption {
    enabled = false  # INTENTIONALLY INSECURE
  }

  tags = var.tags
}

# Data sources for ARN construction
data "aws_region" "current" {}
data "aws_caller_identity" "current" {}

# Variables that should be passed from the parent module
variable "subnet_ids" {
  description = "List of subnet IDs for Elasticsearch domain"
  type        = list(string)
}

variable "security_group_ids" {
  description = "List of security group IDs for Elasticsearch domain"
  type        = list(string)
}

variable "tags" {
  description = "Tags to apply to Elasticsearch resources"
  type        = map(string)
  default     = {}
}

############################
# Outputs
############################
output "elasticsearch_https_endpoint" {
  description = "HTTPS endpoint for Elasticsearch domain"
  value       = aws_elasticsearch_domain.logging.endpoint
}

output "elasticsearch_http_endpoint" {
  description = "HTTP endpoint for Elasticsearch domain"
  value       = "http://${aws_elasticsearch_domain.logging.endpoint}"
}

output "elasticsearch_arn" {
  description = "ARN of the Elasticsearch domain"
  value       = aws_elasticsearch_domain.logging.arn
}

output "endpoint" {
  description = "Elasticsearch domain endpoint (for compatibility)"
  value       = aws_elasticsearch_domain.logging.endpoint
}