terraform {
  required_version = ">= 1.4.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  backend "local" {
    path = "./terraform.tfstate"
  }
}

#############################
#  GLOBAL CONFIG & PROVIDER #
#############################

provider "aws" {
  region                  = var.aws_region
  skip_credentials_validation = false
  skip_metadata_api_check     = false
}

locals {
  project_name = "fake-fintech"
  environment  = var.environment
  tags = {
    Project     = local.project_name
    Environment = local.environment
  }
}

####################
#  NETWORKING VPC  #
####################

# VPC resources are defined in vpc.tf

###############################
#  RELATIONAL DATABASE (RDS)  #
###############################

# RDS resources are defined in rds.tf

#####################################
#  DOCUMENT DATABASE (DOCDB/MONGO)  #
#####################################

# DocumentDB resources are defined in docdb.tf

##########################
#  ELASTICSEARCH (ELASTIC)  #
##########################

# Elasticsearch resources are defined in elasticsearch.tf

############################
#  SECRETS MANAGER VALUES  #
############################

# Secrets Manager resources are defined in secrets.tf

#########################
#  ECS / FARGATE STACK  #
#########################

# ECS resources are defined in ecs.tf

###################
#     OUTPUTS     #
###################

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "rds_endpoint" {
  description = "RDS endpoint"
  value       = aws_db_instance.postgres.endpoint
}

output "docdb_endpoint" {
  description = "DocumentDB endpoint"
  value       = aws_docdb_cluster.docdb.endpoint
}

output "elasticsearch_endpoint" {
  description = "Elasticsearch domain endpoint"
  value       = aws_elasticsearch_domain.logging.endpoint
}

output "ecs_cluster_name" {
  description = "ECS cluster name"
  value       = aws_ecs_cluster.fake_fintech.name
}