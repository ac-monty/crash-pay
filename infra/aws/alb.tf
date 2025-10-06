##########################
# Fake-Fintech – ALB Tier #
##########################
#############################
# >>> Input Configuration <<<
#############################
variable "project_name" {
  description = "Prefix applied to all AWS resources."
  type        = string
}

variable "vpc_id" {
  description = "VPC where the ALB and target groups live."
  type        = string
}

variable "public_subnet_ids" {
  description = "List of public subnet IDs for ALB."
  type        = list(string)
}

variable "ecs_service_ports" {
  description = "TCP port exposed by each ECS service."
  type        = map(number)

  # Default container → port mapping.  
  default = {
    "frontend"           = 3000
    "api-gateway"        = 4000
    "user-service"       = 4001
    "transaction-service"= 4002
    "llm-service"        = 8000
    "rag-service"        = 8080
    "tools-service"      = 8081
    "model-registry"     = 8500
    "mock-external-api"  = 9000
  }
}

#####################
# >>> Security SG <<<
#####################
resource "aws_security_group" "alb_sg" {
  name        = "${var.project_name}-alb-sg"
  description = "Public SG: allow ANY IPv4 HTTP traffic (intentional)."
  vpc_id      = var.vpc_id

  ingress {
    description = "Allow all IPv4 HTTP"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    description = "Allow all outbound"
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project_name}-alb-sg"
  }
}

####################
# >>> ALB Main <<<
####################
resource "aws_lb" "fake_fintech_alb" {
  name               = "${var.project_name}-alb"
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb_sg.id]
  subnets            = var.public_subnet_ids
  idle_timeout       = 60

  tags = {
    Project = var.project_name
  }
}

################################
# >>> Target Groups (one per) <<<
################################
locals {
  # Filter only services we have ports for;
  # ensures TF does not break if map changed elsewhere.
  services = [
    for svc, port in var.ecs_service_ports :
    {
      name = svc
      port = port
    }
  ]
}

resource "aws_lb_target_group" "svc_tg" {
  for_each = {
    for svc in local.services : svc.name => svc
  }

  name_prefix = substr("${each.value.name}-", 0, 6)   # <= 6 chars per AWS constraint
  port        = each.value.port
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"         # Fargate uses awsvpc networking => IP targets

  # Basic health-check; each service should implement /healthz
  health_check {
    protocol            = "HTTP"
    path                = "/healthz"
    matcher             = "200-399"
    interval            = 15
    timeout             = 5
    healthy_threshold   = 2
    unhealthy_threshold = 3
  }

  tags = {
    Project = var.project_name
    Service = each.value.name
  }
}

##############################################
# >>> HTTP Listener (+ Routing Rules) <<<
##############################################
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.fake_fintech_alb.arn
  port              = 80
  protocol          = "HTTP"

  # Default action: send to Front-End
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.svc_tg["frontend"].arn
  }
}

# Path-based routing
#   /api/*                 -> api-gateway
#   /users/*               -> user-service
#   /transactions/*        -> transaction-service
#   /llm/*                 -> llm-service
#   /rag/*                 -> rag-service
#   /tools/*               -> tools-service
#   /registry/*            -> model-registry
#   /mock-bank/*           -> mock-external-api
#
locals {
  routing_rules = [
    { path = "/api/*",            svc = "api-gateway",        priority = 10 },
    { path = "/users/*",          svc = "user-service",       priority = 20 },
    { path = "/transactions/*",   svc = "transaction-service",priority = 30 },
    { path = "/llm/*",            svc = "llm-service",        priority = 40 },
    { path = "/rag/*",            svc = "rag-service",        priority = 50 },
    { path = "/tools/*",          svc = "tools-service",      priority = 60 },
    { path = "/registry/*",       svc = "model-registry",     priority = 70 },
    { path = "/mock-bank/*",      svc = "mock-external-api",  priority = 80 },
  ]
}

resource "aws_lb_listener_rule" "path_based" {
  for_each = {
    for rule in local.routing_rules : rule.svc => rule
  }

  listener_arn = aws_lb_listener.http.arn
  priority     = each.value.priority

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.svc_tg[each.value.svc].arn
  }

  condition {
    path_pattern {
      values = [each.value.path]
    }
  }
}

#############################
# >>> Outputs (Optional) <<<
#############################
output "alb_dns_name" {
  description = "Public DNS name of the Application Load Balancer."
  value       = aws_lb.fake_fintech_alb.dns_name
}

output "alb_security_group_id" {
  description = "Security Group ID attached to the ALB."
  value       = aws_security_group.alb_sg.id
}