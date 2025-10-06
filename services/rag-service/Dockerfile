FROM python:3.11-slim

# Stage 1 – build runtime layer
# -------------------------------------------------------------------
# Intentionally vulnerable RAG Service container
# -------------------------------------------------------------------
#
#  • Runs as root (no USER switch) so any RCE lands with full power.
#  • Ships *.env* secrets inside the final image layer.
#  • Uses `--reload` so attackers can trigger auto-reload DoS.
#  • No pinning / verification of dependency versions.
#
# This baseline is ONLY for security‐research training—never use in prod.
# -------------------------------------------------------------------

ENV PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Copy rag-service code
COPY services/rag-service/ /app

# Copy root .env file for intentional vulnerability
COPY .env /app/.env

# Requirements are unpinned on purpose to illustrate supply-chain risk
RUN pip install -r requirements.txt

EXPOSE 8000

# Start FastAPI with auto-reload (adds more attack surface)
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]