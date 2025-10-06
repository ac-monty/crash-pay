FROM python:3.11-slim

# Stage 1 – builder
# Prevent prompts during package installs
ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install build essentials for any Python packages that need compilation
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

# ------------------------------------------------------------------
# Copy ONLY the llm-service source (not the whole repo) into /app
# This avoids path issues and keeps the final image small.
# ------------------------------------------------------------------

# 1) Requirements first – aids Docker layer caching
COPY services/llm-service/requirements.txt .

# 2) Install Python dependencies
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 3) Copy the service source code
COPY services/llm-service/ /app

# 4) Optionally copy environment file(s)
COPY .env* ./

# Expose service port
EXPOSE 8000

# Default command: start the FastAPI service with Uvicorn
# APM instrumentation is handled directly in the application code
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]