locals {
  services = [
    "api-gateway",
    "user-service",
    "transaction-service",
    "llm-service",
    "rag-service",
    "tools-service",
    "model-retrain",
    "model-registry",
    "mock-external-api"
  ]
}

############################################################
# ECS Task Execution Role (shared across all services)
############################################################
resource "aws_iam_role" "ecs_task_execution_role" {
  name               = "fake-fintech-ecs-task-execution-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_attach" {
  role       = aws_iam_role.ecs_task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

############################################################
# Over-permissive Task Role for each service
############################################################
data "aws_iam_policy_document" "ecs_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

# Inline policy that is intentionally over-permissive
data "aws_iam_policy_document" "over_permissive_policy" {
  statement {
    sid       = "AllowAllSecretsGets"
    actions   = ["secretsmanager:Get*", "secretsmanager:DescribeSecret"]
    resources = ["*"]
  }

  statement {
    sid       = "AllowS3ListEverything"
    actions   = ["s3:ListAllMyBuckets", "s3:ListBucket"]
    resources = ["*"]
  }
}

resource "aws_iam_role" "service_task_role" {
  for_each           = toset(local.services)
  name               = "fake-fintech-${each.key}-task-role"
  assume_role_policy = data.aws_iam_policy_document.ecs_assume_role.json
}

resource "aws_iam_role_policy" "service_task_policy" {
  for_each = aws_iam_role.service_task_role

  name   = "fake-fintech-${each.key}-over-permissive-policy"
  role   = each.value.id
  policy = data.aws_iam_policy_document.over_permissive_policy.json
}