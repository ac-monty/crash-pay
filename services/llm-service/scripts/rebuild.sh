#!/usr/bin/env bash

# =============================================================================
# Docker Rebuild Script for LLM Service
# =============================================================================
# This script rebuilds the Docker container with --no-cache option
# Useful when updating files as mentioned by the user
# =============================================================================

set -e

echo "-> Changing directory to root"
# Move to the directory where the script is located, then go one up
cd "$(dirname "$0")/.."

echo "🔄 Rebuilding LLM Service Docker Container..."
echo "   Using --no-cache for clean rebuild"
echo ""

# Stop and remove existing container if running
echo "-> Stopping and removing existing container"
docker stop llm-service 2>/dev/null || true
docker rm llm-service 2>/dev/null || true

# Build with no cache
echo "🏗️  Building Docker image..."
docker build -t llm-service . --no-cache

# Run the container
echo "🚀 Starting LLM Service..."
docker run -d \
  --name llm-service \
  -p 8000:8000 \
  --env-file .env \
  llm-service

echo ""
echo "✅ LLM Service rebuilt and started successfully!"
echo "   Service available at: http://localhost:8000"
echo "   API Documentation: http://localhost:8000/docs"
echo ""
echo "   To view logs: docker logs -f llm-service"
echo "   To stop: docker stop llm-service"
echo "   To test: ./test_api.sh" 