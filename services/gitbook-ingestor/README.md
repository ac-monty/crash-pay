# GitBook Ingestor Service

This service fetches content from GitBook spaces and indexes it into Pinecone vector databases for RAG (Retrieval Augmented Generation) functionality.

## Features

- **Full Sync**: Downloads all pages from configured GitBook space collections on startup
- **Real-time Updates**: Webhook endpoint for live updates when GitBook content changes
- **Collection-based Routing**: Routes pages to different Pinecone indices based on collection paths
- **Automatic Vectorization**: Uses sentence-transformers to create embeddings

## Configuration

### Required Environment Variables

```env
# GitBook Personal Access Token
# Get from: https://app.gitbook.com/account/developer
GITBOOK_API="gb_api_your_token_here"

# GitBook Space ID
# From URL: https://app.gitbook.com/o/ORG_ID/s/SPACE_ID
GITBOOK_SPACE_ID="your-space-id-here"

# Pinecone Configuration
PINECONE_API_KEY="your-pinecone-api-key"
PINECONE_ENVIRONMENT="us-east-1"

# Pinecone Index Names (optional, defaults shown)
PINECONE_INDEX_RAG="fake-fintech-rag-corpus"
PINECONE_INDEX_NONRAG="fake-fintech-nonrag-corpus"
```

## GitBook Space Structure

The service expects a single GitBook space with two collections:

```
Your GitBook Space
├── Root Pages (/) → RAG Index
│   ├── account_services.md
│   ├── bank_information.md
│   └── troubleshooting_faq.md
│
└── non-rag-corpus/ → Non-RAG Index
    ├── confidential.md
    ├── internal-docs.md
    └── sensitive-info.md
```

## Collection Routing

- **Root-level pages**: Go to the "rag" Pinecone index (default: `fake-fintech-rag-corpus`)
- **non-rag-corpus/ pages**: Go to the "nonrag" Pinecone index (default: `fake-fintech-nonrag-corpus`)

## Webhook Setup (Optional)

For real-time updates, configure GitBook webhooks:

1. Go to your GitBook space settings
2. Navigate to Integrations → Webhooks
3. Add webhook URL: `http://your-host:8020/webhook`
4. Enable events: `page.published`, `page.updated`, `page.deleted`

## API Endpoints

- `GET /health` - Health check
- `POST /webhook` - GitBook webhook handler

## Docker Usage

```bash
# Build
docker-compose build gitbook-ingestor

# Run
docker-compose up -d gitbook-ingestor

# Logs
docker logs crash-pay-gitbook-ingestor
```

## Embedding Model

Uses `sentence-transformers/all-mpnet-base-v2` for creating 768-dimensional embeddings compatible with Pinecone's cosine similarity.

## Security Note

This service is designed for internal use within the crash-pay security testing environment. Ensure proper network isolation in production deployments.