FROM python:3.11-slim
WORKDIR /app
COPY services/gitbook-ingestor/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt
COPY services/gitbook-ingestor /app
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8020"]