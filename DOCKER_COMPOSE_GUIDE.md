# 🐳 Crash-Pay Docker Compose Guide

## Overview

The Crash-Pay application uses a **unified `docker-compose.yml`** that orchestrates:
- ✅ **9 Business Services** (API Gateway, LLM Service, Tools Service, etc.)
- ✅ **Complete Observability Stack** (Elasticsearch, Kibana, APM, Metricbeat, Filebeat)
- ✅ **3 Data Stores** (PostgreSQL, MongoDB, Qdrant)
- ✅ **React Frontend** with hot reloading
- ✅ **APM Instrumentation** for all services
- ✅ **2 Dedicated Networks** for service isolation

## 🚀 Quick Start

### 1. Prerequisites
```bash
# Ensure Docker and Docker Compose are installed
docker --version  # Should be 20.10+
docker-compose --version  # Should be 1.29+

# Ensure you have the environment file
cp env.template .env
# Edit .env with your API keys (see API Keys section below)
```

### 2. Clean No-Cache Build (Recommended)
```bash
# Clean slate - removes all existing containers and networks
export DOCKER_NO_CACHE=true
docker stop $(docker ps -aq --filter "name=crash-pay") 2>/dev/null || true
docker rm $(docker ps -aq --filter "name=crash-pay") 2>/dev/null || true
docker network rm crash-pay-business crash-pay-observability 2>/dev/null || true

# Start everything with fresh builds
docker-compose up --build -d
```

### 3. Quick Start (Using cached builds)
```bash
# For subsequent runs after initial build
docker-compose up -d
```

### 4. Monitor Startup
```bash
# Watch all services start up
docker-compose logs -f

# Check service status
docker-compose ps

# Wait for all services to be healthy (may take 2-3 minutes)
./test-no-cache-build.sh
```

## 🏗️ Service Architecture

### 🔗 Networks
The compose file creates **exactly 2 networks**:

1. **`crash-pay-business`** - Service-to-service communication
2. **`crash-pay-observability`** - APM and monitoring data flow

All business services are connected to both networks to enable:
- Business logic communication via `crash-pay-business`
- APM data collection via `crash-pay-observability`

### 🏢 Business Services

| Service | Port | Status | Purpose | Critical Endpoints |
|---------|------|--------|---------|-------------------|
| **API Gateway** | 8080 | Entry Point | Authentication, routing | `/health`, `/auth/login` |
| **LLM Service** | 8000 | Multi-LLM | 14+ providers, function calling | `/chat`, `/provider` |
| **User Service** | 8083 | Auth | User management | `/register`, `/login` |
| **Transaction Service** | 8084 | Banking | Money transfers | `/accounts`, `/transfer` |
| **Tools Service** | 4003 | **DANGEROUS** | Shell + payments | `/shell`, `/payments` |
| **RAG Service** | 4001 | Document Search | Unauth'd retrieval | `/search`, `/documents` |
| **Model Registry** | 8050 | Model Storage | Unsigned models | `/models`, `/download` |
| **Mock External API** | 9001 | Simulation | Fake bank partner | `/verify`, `/pay` |
| **React Frontend** | 5173 | Web UI | Chat interface | Built-in XSS vulns |

### 🔍 Observability Stack

| Component | Port | Purpose | Access URL |
|-----------|------|---------|------------|
| **Elasticsearch** | 9200 | Log storage | http://localhost:9200 |
| **Kibana** | 5601 | Visualization | http://localhost:5601 |
| **APM Server** | 8200 | Performance monitoring | http://localhost:8200 |
| **Metricbeat** | - | System metrics | (background) |
| **Filebeat** | - | Log collection | (background) |

### 🗄️ Data Stores

| Store | Port | Purpose | Technology |
|-------|------|---------|------------|
| **PostgreSQL** | 5432 | User & transaction data | PostgreSQL 15 |
| **MongoDB** | 27018 | Application logs | MongoDB 7.0 |
| **Qdrant** | 6335 | Vector embeddings | Qdrant latest |

## 🔑 API Keys Configuration

### Required API Keys
Edit your `.env` file with LLM provider API keys:

```bash
# OpenAI (Required for most functionality)
OPENAI_API_KEY=sk-proj-...

# Optional but recommended providers
ANTHROPIC_API_KEY=sk-ant-...
GOOGLE_API_KEY=AIza...
COHERE_API_KEY=...

# Azure OpenAI (if using Azure)
AZURE_OPENAI_API_KEY=...
AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
AZURE_OPENAI_DEPLOYMENT_NAME=gpt-4

# Other providers (optional)
MISTRAL_API_KEY=...
TOGETHER_API_KEY=...
REPLICATE_API_TOKEN=...
HUGGINGFACE_API_TOKEN=...
```

### No-Cache Builds
Set environment variable for fresh builds:
```bash
# In your shell
export DOCKER_NO_CACHE=true

# Or in .env file
echo "DOCKER_NO_CACHE=true" >> .env
```

## 📊 Testing the Setup

### 1. Health Check All Services
```bash
# Core business services
curl http://localhost:8080/health    # API Gateway
curl http://localhost:8000/healthz   # LLM Service  
curl http://localhost:8083/health    # User Service
curl http://localhost:8084/health    # Transaction Service
curl http://localhost:4003/health    # Tools Service
curl http://localhost:4001/health    # RAG Service

# Data stores
curl http://localhost:9200/_cluster/health  # Elasticsearch
curl http://localhost:8200/                 # APM Server
```

### 2. Test LLM Integration
```bash
# Check available providers
curl http://localhost:8000/provider

# Test chat functionality (requires API key)
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"prompt":"Hello, how are you?"}'

# Check model switching
curl -X POST http://localhost:8000/switch-provider?provider=anthropic
```

### 3. Test Dangerous Tools (⚠️ Use with caution)
```bash
# Shell execution (DANGEROUS - command injection vulnerable)
curl "http://localhost:4003/shell?cmd=whoami"
curl "http://localhost:4003/shell?cmd=ls -la"

# Payment processing (mock but dangerous pattern)
curl -X POST http://localhost:4003/payments \
  -H "Content-Type: application/json" \
  -d '{"from_account":"123","to_account":"456","amount":100}'
```

### 4. Test RAG Service (Exposes sensitive data)
```bash
# Search sensitive documents (intentionally vulnerable)
curl -X POST http://localhost:4001/search \
  -H "Content-Type: application/json" \
  -d '{"query":"customer data","k":5}'

# List all documents (no authentication)
curl http://localhost:4001/documents
```

### 5. Generate APM Data
```bash
# Generate some transactions for monitoring
for i in {1..10}; do
  curl "http://localhost:4003/shell?cmd=echo test $i"
  sleep 1
done

# Check APM data in Kibana
open http://localhost:5601/app/apm
```

## 🐛 Troubleshooting

### Common Issues

#### 1. Port Conflicts
```bash
# Check what's using ports
lsof -i :8080 -i :5601 -i :9200 -i :5432

# Stop conflicting services
sudo systemctl stop postgresql  # If running locally
sudo systemctl stop elasticsearch
brew services stop postgresql  # On macOS
```

#### 2. Memory Issues
```bash
# Elasticsearch requires significant memory
# Increase Docker memory to at least 4GB
# Docker Desktop > Settings > Resources > Memory > 4GB+

# Check current memory usage
docker stats
```

#### 3. Build Cache Issues
```bash
# Force complete rebuild
export DOCKER_NO_CACHE=true
docker-compose down -v  # Remove volumes too
docker system prune -a  # Clean up everything
docker-compose up --build -d
```

#### 4. Network Conflicts
```bash
# Clean up networks
docker network prune -f

# Restart Docker daemon (if needed)
sudo systemctl restart docker  # Linux
# Restart Docker Desktop on macOS/Windows
```

#### 5. Service Startup Order Issues
```bash
# Some services depend on databases being ready
# Wait for databases first
docker-compose up -d postgres mongodb qdrant elasticsearch
sleep 30

# Then start the rest
docker-compose up -d
```

### Logs and Debugging

```bash
# View logs for specific service
docker-compose logs -f llm-service
docker-compose logs -f api-gateway
docker-compose logs -f elasticsearch

# View all logs with timestamps
docker-compose logs -f -t

# Check service status and health
docker-compose ps
docker-compose exec api-gateway curl -f http://localhost:8080/health

# Get into a container for debugging
docker-compose exec llm-service bash
docker-compose exec postgres psql -U crashpay -d crashpay
```

### Performance Monitoring
```bash
# Monitor resource usage
docker stats

# Check Elasticsearch cluster health
curl http://localhost:9200/_cluster/health?pretty

# Monitor APM data
curl http://localhost:8200/stats

# Check Kibana index patterns
curl http://localhost:5601/api/status
```

## ⚙️ Configuration Options

### Environment Variables
Key environment variables you can customize in `.env`:

```bash
# LLM Configuration
LLM_PROVIDER=openai  # Default provider
LLM_MODEL=gpt-4o     # Default model
LLM_STREAMING=false  # Enable streaming responses
SYSTEM_PROMPT_ENABLED=true  # Enable system prompts

# Database Configuration
POSTGRES_DB=crashpay
POSTGRES_USER=crashpay
POSTGRES_PASSWORD=crashpay123

MONGO_INITDB_ROOT_USERNAME=admin
MONGO_INITDB_ROOT_PASSWORD=admin123
MONGO_INITDB_DATABASE=crashpay

# Observability Configuration
ELASTIC_APM_SERVICE_NAME=crash-pay
ELASTIC_APM_SERVER_URL=http://apm-server:8200
ELASTIC_APM_ENVIRONMENT=development

# Build Configuration
DOCKER_NO_CACHE=false  # Set to true for clean builds
```

### Volume Mounts
Persistent data is stored in Docker volumes:

```yaml
# Persistent Data Volumes
volumes:
  postgres_data:      # PostgreSQL database files
  mongodb_data:       # MongoDB database files
  qdrant_data:        # Vector database files
  elasticsearch_data: # Elasticsearch indices and logs
  
# Configuration Mounts (read-only)
volumes:
  - ./docs/rag_corpus:/app/docs:ro           # RAG documents
  - ./training-drops:/app/training-drops     # Model training data
  - ./shared/auth:/app/shared/auth:ro        # Shared auth utilities
```

### Custom Service Configuration
To modify service behavior, edit the respective service directories:

```bash
# API Gateway configuration
services/api-gateway/src/app.js

# LLM Service configuration  
services/llm-service/main.py
services/llm-service/llm_loader.py

# Add new RAG documents
docs/rag_corpus/your-document.pdf

# Add training data for model poisoning
training-drops/malicious-training.jsonl
```

## 🔄 Development Workflow

### 1. Making Code Changes
```bash
# For hot reloading (Node.js services)
docker-compose restart api-gateway

# For Python services (FastAPI with --reload)
docker-compose restart llm-service

# For frontend changes (Vite handles HMR automatically)
# No restart needed - changes appear immediately
```

### 2. Database Management
```bash
# Access PostgreSQL
docker-compose exec postgres psql -U crashpay -d crashpay

# Access MongoDB
docker-compose exec mongodb mongosh --username admin --password admin123

# Reset databases (⚠️ DESTRUCTIVE)
docker-compose down -v
docker-compose up -d
```

### 3. Observability Management
```bash
# Reset Elasticsearch indices
curl -X DELETE http://localhost:9200/*

# Import Kibana dashboards (if available)
curl -X POST "localhost:5601/api/saved_objects/_import" \
  -H "kbn-xsrf: true" -H "Content-Type: application/json" \
  --form file=@kibana-dashboards.ndjson

# Check APM service map
open http://localhost:5601/app/apm/service-map
```

## 🚨 Security Warnings

### ⚠️ EXTREMELY DANGEROUS ENDPOINTS
These endpoints are intentionally vulnerable - **DO NOT** expose to the internet:

```bash
# Shell execution with no validation
curl "http://localhost:4003/shell?cmd=rm -rf /"

# Payment processing with no authorization
curl -X POST http://localhost:4003/payments -d '{"amount":999999}'

# Sensitive document access with no authentication
curl http://localhost:4001/search -d '{"query":"confidential"}'

# Model switching that could load malicious models
curl -X POST http://localhost:8000/switch-provider?provider=malicious
```

### 🔒 Development vs Production

**Current Setup (Development/Research):**
- ❌ No authentication on critical endpoints
- ❌ CORS allows all origins
- ❌ Verbose error messages expose internal details
- ❌ Plain text secrets in environment variables
- ❌ No rate limiting or input validation
- ❌ Direct shell access via HTTP
- ❌ Sensitive documents publicly accessible

**Production Requirements (If Used):**
- ✅ OAuth 2.0/JWT authentication
- ✅ CORS restricted to specific origins
- ✅ Error message sanitization
- ✅ Secrets Manager integration
- ✅ Rate limiting and WAF protection
- ✅ Audit logging for all operations
- ✅ TLS encryption for all communications

## 📁 Directory Structure

```
crash-pay-app/
├── docker-compose.yml          # Main orchestration file
├── .env                        # Environment variables
├── env.template               # Environment template
│
├── services/                  # Business logic services
│   ├── api-gateway/          # Central routing + auth
│   ├── llm-service/          # Multi-provider LLM
│   ├── user-service/         # User management
│   ├── transaction-service/  # Banking operations
│   ├── tools-service/        # DANGEROUS shell + payments
│   ├── rag-service/          # Document retrieval
│   ├── model-registry/       # Model storage
│   ├── model-retrain/        # Training data monitoring
│   └── mock-external-api/    # External service simulation
│
├── frontend/                 # React web interface
│   ├── src/                 # Source code
│   └── public/              # Static assets
│
├── infra/                   # Infrastructure configs
│   ├── aws/                # Terraform for AWS deployment
│   └── observability/      # Elastic stack configs
│
├── docs/                   # Documentation
│   └── rag_corpus/        # Sensitive documents (intentional)
│
├── shared/                 # Shared utilities
│   ├── auth/              # Authentication helpers
│   └── utils/             # Common utilities
│
└── training-drops/        # Model training data (poisoning vector)
```

## 🔄 Migration from Old Setup

If upgrading from previous versions:

### Archived Files
These files have been moved to `.archive/` and are no longer used:
- `docker-compose.observability.yml`
- `docker-compose.override.yml`
- `infra/local/docker-compose.yml`

### New Features
- **Single Configuration**: Everything in main `docker-compose.yml`
- **Network Isolation**: Dedicated business and observability networks
- **Enhanced APM**: Full service instrumentation
- **Model Registry**: Local model storage and serving
- **Training Monitoring**: Automatic model retraining

### Migration Steps
```bash
# 1. Stop old setup
docker-compose -f docker-compose.observability.yml down
docker-compose down

# 2. Clean up old resources
docker network prune -f
docker volume prune -f

# 3. Start new unified setup
docker-compose up --build -d
```

## 📈 Performance Tips

### 1. Build Optimization
```bash
# Use BuildKit for faster builds
export DOCKER_BUILDKIT=1
export COMPOSE_DOCKER_CLI_BUILD=1

# Parallel builds
docker-compose build --parallel

# Layer caching
docker-compose build --build-arg BUILDKIT_INLINE_CACHE=1
```

### 2. Resource Allocation
```bash
# Allocate more resources to Elasticsearch
# In docker-compose.yml, adjust:
# mem_limit: 2g
# cpus: 2.0
```

### 3. Selective Service Startup
```bash
# Start only core services for development
docker-compose up -d postgres mongodb api-gateway llm-service frontend

# Add observability when needed
docker-compose up -d elasticsearch kibana apm-server
```

## 🎯 Next Steps

After successful setup:

1. **Access the Frontend**: http://localhost:5173
2. **Explore APIs**: Use the endpoints documented above
3. **Monitor with Kibana**: http://localhost:5601
4. **Test Security Vulnerabilities**: Follow responsible research practices
5. **Review Service Documentation**: See `SERVICES_AND_INFRA.md`

## 📞 Support

For issues and questions:
- Check logs: `docker-compose logs -f [service-name]`
- Review health checks: `docker-compose ps`
- Validate configuration: `docker-compose config`
- Monitor resources: `docker stats`

---

**⚠️ Warning**: This application contains intentional security vulnerabilities for research purposes. Never deploy to production or expose to the internet without proper security hardening.
