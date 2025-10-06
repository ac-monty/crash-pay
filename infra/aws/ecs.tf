# ECS cluster
resource "aws_ecs_cluster" "fake_fintech" {
  name = "fake-fintech-cluster"
}

# -----------------------------------------------------------
# IAM — general-purpose Fargate execution role (over-privileged
# on purpose to mirror misconfiguration described in spec)
# -----------------------------------------------------------
data "aws_iam_policy_document" "task_execution_assume_role" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["ecs-tasks.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "task_execution_role" {
  name               = "fake-fintech-task-execution"
  assume_role_policy = data.aws_iam_policy_document.task_execution_assume_role.json
}

# Attach the **managed** AWS policy plus an intentionally
# broad inline statement (deliberately weak per lab goals)
resource "aws_iam_role_policy_attachment" "managed_execution" {
  role       = aws_iam_role.task_execution_role.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

resource "aws_iam_role_policy" "insecure_extra_perms" {
  name = "fake-fintech-insecure-extra"
  role = aws_iam_role.task_execution_role.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      # Excessive access intentionally granted
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue", "kms:Decrypt"]
        Resource = "*"
      },
      {
        Effect   = "Allow"
        Action   = ["s3:*"]
        Resource = "*"
      }
    ]
  })
}

# -----------------------------------------------------------
# Security Group for ECS Services
# -----------------------------------------------------------
resource "aws_security_group" "ecs_services" {
  name        = "fake-fintech-ecs-services"
  description = "Security group for ECS Fargate services"
  vpc_id      = aws_vpc.main.id

  # Allow all outbound traffic
  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  # Allow inbound from ALB
  ingress {
    from_port       = 0
    to_port         = 65535
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  # Allow internal communication between services
  ingress {
    from_port = 0
    to_port   = 65535
    protocol  = "tcp"
    self      = true
  }

  tags = {
    Name        = "fake-fintech-ecs-services"
    Project     = "fake-fintech"
    Environment = var.environment
  }
}

# -----------------------------------------------------------
# Local definitions — map each micro-service to its task-def
# JSON file and desired task count.  The JSONs must exist under
# infra/aws/ecs-task-defs/   (rendered by CI or hand-written)
# -----------------------------------------------------------
locals {
  services = {
    "frontend"           = { file = "${path.module}/ecs-task-defs/frontend.json",           desired = 1 }
    "api-gateway"        = { file = "${path.module}/ecs-task-defs/api-gateway.json",        desired = 2 }
    "user-service"       = { file = "${path.module}/ecs-task-defs/user-service.json",       desired = 1 }
    "transaction-service"= { file = "${path.module}/ecs-task-defs/transaction-service.json",desired = 1 }
    "llm-service"        = { file = "${path.module}/ecs-task-defs/llm-service.json",        desired = 2 }
    "rag-service"        = { file = "${path.module}/ecs-task-defs/rag-service.json",        desired = 1 }
    "tools-service"      = { file = "${path.module}/ecs-task-defs/tools-service.json",      desired = 1 }
    "model-retrain"      = { file = "${path.module}/ecs-task-defs/model-retrain.json",      desired = 1 }
    "model-registry"     = { file = "${path.module}/ecs-task-defs/model-registry.json",     desired = 1 }
    "mock-external-api"  = { file = "${path.module}/ecs-task-defs/mock-external-api.json",  desired = 1 }
  }
}

# -----------------------------------------------------------
# ECS task-definitions (from pre-rendered JSON)
# -----------------------------------------------------------
resource "aws_ecs_task_definition" "service" {
  for_each             = local.services

  family               = "fake-fintech-${each.key}"
  requires_compatibilities = ["FARGATE"]
  network_mode         = "awsvpc"
  cpu                  = 256
  memory               = 512

  # Load the container definition JSON blob directly
  container_definitions = file(each.value.file)

  execution_role_arn   = aws_iam_role.task_execution_role.arn
  task_role_arn        = aws_iam_role.task_execution_role.arn  # same role for simplicity / weak-default
}

# -----------------------------------------------------------
# ECS Fargate services
# -----------------------------------------------------------
resource "aws_ecs_service" "service" {
  for_each        = local.services

  name            = "fake-fintech-${each.key}"
  cluster         = aws_ecs_cluster.fake_fintech.id
  desired_count   = each.value.desired
  launch_type     = "FARGATE"

  task_definition = aws_ecs_task_definition.service[each.key].arn

  network_configuration {
    subnets         = [for s in aws_subnet.private : s.id]
    security_groups = [aws_security_group.ecs_services.id]
    assign_public_ip = false
  }

  lifecycle {
    ignore_changes = [
      desired_count  # allow dynamic scaling without terraform drift
    ]
  }

  deployment_minimum_healthy_percent = 50
  deployment_maximum_percent         = 200

  enable_execute_command = true
}