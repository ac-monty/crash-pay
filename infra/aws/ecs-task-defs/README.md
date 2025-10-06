# ECS Task Definitions

This directory contains AWS ECS Fargate task definitions for all services in the Fake-Fintech OWASP-LLM testbed.

## Directory Structure

```
infra/aws/ecs-task-defs/
├── api-gateway.json          # Main API gateway (port 3030)
├── user-service.json         # User management (port 8081)
├── transaction-service.json  # Financial transactions (port 4002)
├── llm-service.json          # LLM provider router (port 8000)
├── rag-service.json          # RAG document search (port 8001)
├── tools-service.json        # Shell & payments tools (port 8002)
├── frontend.json             # React frontend (port 80)
├── model-registry.json       # Unsigned model serving (port 8050)
├── model-retrain.json        # Auto model retraining (background)
├── mock-external-api.json    # Mock banking partner (port 4005)
└── README.md                 # This file
```

## Configuration Overview

### Common Patterns

All task definitions follow these patterns:

- **Platform**: Linux x86_64 on AWS Fargate
- **Resource Allocation**: 256-512 CPU units, 512-1024 MB memory
- **Networking**: awsvpc mode with security groups
- **Logging**: CloudWatch Logs with Filebeat sidecars for Elastic Stack
- **Health Checks**: HTTP curl to `/health` endpoints
- **Secrets**: AWS Secrets Manager for sensitive configuration

### Environment Variables vs Secrets

#### Environment Variables (Public Configuration)
- Service ports and networking
- Feature flags and behavior settings
- Non-sensitive operational parameters

#### AWS Secrets Manager (Sensitive Data)
- API keys for LLM providers
- Database credentials
- JWT signing secrets
- OAuth tokens and certificates

### Port Mapping

| Service | Container Port | Description |
|---------|----------------|-------------|
| api-gateway | 3030 | Main API gateway |
| user-service | 8081 | User management |
| transaction-service | 4002 | Financial operations |
| llm-service | 8000 | LLM provider router |
| rag-service | 8001 | RAG document search |
| tools-service | 8002 | Shell & payment tools |
| model-registry | 8050 | Model serving |
| mock-external-api | 4005 | Mock banking API |
| frontend | 80 | React web application |

## Deployment

### Prerequisites

1. **AWS Account Setup**
   - ECS cluster with Fargate capacity
   - VPC with public/private subnets
   - Application Load Balancer
   - ECR repositories for each service

2. **Secrets Manager Setup**
   ```bash
   # Example secret creation
   aws secretsmanager create-secret \
     --name "fake-fintech/openai-api-key" \
     --description "OpenAI API key for LLM service" \
     --secret-string "sk-proj-..."
   ```

3. **CloudWatch Log Groups**
   ```bash
   # Create log groups for all services
   aws logs create-log-group --log-group-name "/ecs/fake-fintech/api-gateway"
   aws logs create-log-group --log-group-name "/ecs/fake-fintech/llm-service"
   # ... repeat for all services
   ```

### Task Registration

```bash
# Register task definitions
for task_def in *.json; do
  # Replace placeholders with actual values
  sed -e "s/<AWS_ACCOUNT_ID>/123456789012/g" \
      -e "s/<AWS_REGION>/us-east-1/g" \
      -e "s/<AWS_ELASTICSEARCH_ENDPOINT>/search-fake-fintech.us-east-1.es.amazonaws.com/g" \
      "$task_def" > "processed-$task_def"
  
  # Register with ECS
  aws ecs register-task-definition --cli-input-json "file://processed-$task_def"
done
```

### Service Creation

```bash
# Create ECS services
aws ecs create-service \
  --cluster fake-fintech-cluster \
  --service-name api-gateway \
  --task-definition fake-fintech-api-gateway:1 \
  --desired-count 2 \
  --launch-type FARGATE \
  --network-configuration "awsvpcConfiguration={subnets=[subnet-abc123],securityGroups=[sg-abc123],assignPublicIp=ENABLED}"
```

## Security Considerations

### Intentional Vulnerabilities

These task definitions maintain educational security vulnerabilities:

- **OWASP-LLM-05**: Unsigned models served from model-registry
- **OWASP-LLM-07**: Dangerous tools enabled in tools-service
- **OWASP-LLM-08**: Over-privileged IAM roles
- **OWASP-LLM-09**: Insecure plugin architecture

### Production Hardening

For non-educational use, implement:

- **Least Privilege IAM**: Narrow task role permissions
- **Network Segmentation**: Private subnets with NAT gateways
- **WAF Protection**: Application Load Balancer WAF rules
- **Secrets Rotation**: Automated API key rotation
- **Container Scanning**: ECR vulnerability scanning

## Monitoring & Observability

### CloudWatch Integration

- **Metrics**: CPU, memory, network utilization
- **Logs**: Application logs and access logs
- **Alarms**: Service health and performance thresholds

### Elastic Stack Integration

- **Filebeat Sidecars**: Forward logs to Elasticsearch
- **Log Correlation**: Unified logging across services
- **Dashboards**: Operational visibility in Kibana

## Troubleshooting

### Common Issues

1. **Task Startup Failures**
   ```bash
   # Check task logs
   aws ecs describe-tasks --cluster fake-fintech-cluster --tasks <task-arn>
   aws logs get-log-events --log-group-name "/ecs/fake-fintech/api-gateway" --log-stream-name "<stream-name>"
   ```

2. **Health Check Failures**
   - Verify container port mappings
   - Check security group rules
   - Validate health check endpoints

3. **Secrets Access Issues**
   - Verify IAM task role permissions
   - Check Secrets Manager secret ARNs
   - Validate secret value formats

### Useful Commands

```bash
# List running tasks
aws ecs list-tasks --cluster fake-fintech-cluster

# Get service status
aws ecs describe-services --cluster fake-fintech-cluster --services api-gateway

# View task definition
aws ecs describe-task-definition --task-definition fake-fintech-api-gateway:latest

# Update service with new task definition
aws ecs update-service --cluster fake-fintech-cluster --service api-gateway --task-definition fake-fintech-api-gateway:2
```

## Template Placeholders

When deploying, replace these placeholders:

- `<AWS_ACCOUNT_ID>`: Your 12-digit AWS account ID
- `<AWS_REGION>`: Target AWS region (e.g., us-east-1)
- `<AWS_ELASTICSEARCH_ENDPOINT>`: Elasticsearch domain endpoint

## Related Documentation

- [AWS ECS Task Definition Reference](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_definitions.html)
- [AWS Secrets Manager Integration](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/specifying-sensitive-data-secrets.html)
- [Fake-Fintech Architecture Guide](../../README.md) 