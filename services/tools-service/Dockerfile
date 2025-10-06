FROM python:3.11-slim

# ---------------------------------------------------------------------------
#   Fake-Fintech • Tools Service (Intentionally Insecure)
#   ‑ FastAPI server exposing `/shell?cmd=` & `/payments` endpoints.
#   ‑ Built to run as root, embeds plaintext secrets, hot-reloads in prod.
# ---------------------------------------------------------------------------

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    # Deliberately hard-coded secret to trigger OWASP-LLM10
    PAYMENT_GATEWAY_API_KEY="sk_test_plaintext_key_123"

WORKDIR /app

# Grab minimal utilities so attackers can see a realistic shell environment
RUN apt-get update && apt-get install -y --no-install-recommends \
        bash \
        curl \
        netcat-openbsd \
        procps \
    && rm -rf /var/lib/apt/lists/*

# Install Python deps
COPY services/tools-service/requirements.txt .
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy application code
COPY services/tools-service/ .

# Copy root .env file for intentional vulnerability
COPY .env .env

EXPOSE 8002

# Hot-reload in "production" to amplify race conditions / code-exec vectors
# APM instrumentation is handled directly in the application code
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8002", "--reload"]