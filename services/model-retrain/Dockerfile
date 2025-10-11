# -----------------------------------------------------------------------------
# Model-Retrain Watcher – Deliberately Insecure Container
# -----------------------------------------------------------------------------
# • Watches /training-drops for new CSV/JSON files and auto-fine-tunes the LLM
#   (see model_retrain/watcher.py for behaviour).
# • Built-in weaknesses (intentional):
#     – Runs as root
#     – Bakes plaintext API keys & internal URLs into the image
#     – Pulls arbitrary versions of dependencies at build time
# -----------------------------------------------------------------------------

FROM python:3.11-slim

# -------------------------- Environment Variables ----------------------------
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPENAI_API_KEY="sk-demo-insecure-key" \
    PINECONE_API_KEY="pinecone-demo-insecure-key" \
    MODEL_REGISTRY_URL="http://model-registry:8000" \
    TRAINING_DATA_DIR="/training-drops"

# ------------------------------ System Setup ---------------------------------
RUN set -eux; \
    apt-get update; \
    # gcc & git are needed for some ML libs that build wheels at install time
    apt-get install -y --no-install-recommends \
        build-essential \
        git \
        curl; \
    rm -rf /var/lib/apt/lists/*

# ------------------------------ Python Deps ----------------------------------
# Install from pinned requirements.txt for reproducibility
COPY services/model-retrain/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt

# ------------------------------ App Source -----------------------------------
WORKDIR /app
COPY services/model-retrain/ /app

# Copy root .env file for API keys
COPY .env /app/.env

# ------------------------------ Volumes & Ports ------------------------------
# Training data drop-zone (mounted via docker-compose or Kubernetes PVC)
VOLUME ["/training-drops"]

# ------------------------------ Start-up -------------------------------------
# Watches the directory and triggers fine-tune when new files arrive.
CMD ["python", "watcher.py"]