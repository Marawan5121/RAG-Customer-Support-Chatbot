# Customer Support RAG-Powered Intelligent Chatbot

Production-ready scaffold for a Retrieval-Augmented Generation (RAG) customer
support chatbot. Backend in **FastAPI**, frontend in **Next.js**, orchestrated
locally with **Docker Compose**.

## Tech stack

| Layer | Technology |
|-------|-----------|
| Backend | FastAPI (Python 3.11), modular routers + services |
| Frontend | Next.js 14 (App Router, TypeScript) |
| Vector retrieval | Azure AI Search — hybrid (vector + BM25) + semantic ranking |
| Chat history | Azure Cosmos DB |
| Response cache | Azure Cache for Redis (local Redis container in dev) |
| LLM + embeddings | Google AI Studio — Gemini 1.5 Flash + 768-dim embeddings |

## Project structure

```
.
├── docker-compose.yml          # backend + frontend + redis
├── .env.example                # points to backend/.env.example
├── backend/
│   ├── Dockerfile
│   ├── requirements.txt        # FastAPI + Azure SDKs + google-generativeai
│   ├── .env.example
│   └── app/
│       ├── main.py             # app factory + lifespan service wiring
│       ├── core/               # config.py (env loaders), logging.py
│       ├── api/
│       │   ├── deps.py         # dependency providers
│       │   └── routers/        # health, chat, sessions
│       ├── services/           # search, cosmos, cache, llm (placeholders)
│       └── schemas/            # chat & session pydantic models
└── frontend/
    ├── Dockerfile              # multi-stage, standalone output
    ├── package.json
    ├── app/                    # layout, page (chat UI), globals.css
    └── lib/api.ts              # backend API client
```

The backend follows a **router → service** separation: routers handle HTTP
concerns only, while each external integration lives behind a dedicated service
class (`SearchService`, `CosmosService`, `CacheService`, `LLMService`). Services
are instantiated once in the lifespan handler and injected via `app.state`.

## Getting started

1. Configure the backend environment:
   ```bash
   cp backend/.env.example backend/.env
   # then fill in the Azure AI Search, Cosmos DB and Google API values
   ```

2. (Optional) configure the frontend:
   ```bash
   cp frontend/.env.local.example frontend/.env.local
   ```

3. Launch the stack:
   ```bash
   docker compose up --build
   ```

   - Backend API: http://localhost:8000 (docs at `/docs`)
   - Frontend UI: http://localhost:3000
   - Health check: http://localhost:8000/api/v1/health

## Configuration notes

- **Azure AI Search & Cosmos DB** are managed cloud services — only their
  endpoints/keys are needed (no local container). **Redis** runs as a local
  container in dev; switch to Azure Cache for Redis by setting `REDIS_HOST`,
  `REDIS_PORT=6380` and `REDIS_SSL=true`.
- **Embedding dimension is 768** (Google `text-embedding-004`). The Azure AI
  Search index `content_vector` field must be created with 768 dimensions.
- Every service degrades gracefully when its credentials are absent, so the app
  boots and `/health` reports per-component readiness even before all
  integrations are configured.

## Implementation status

This is the **structural scaffold** (Milestone 1). The RAG pipeline (embedding,
hybrid retrieval, generation, faithfulness check, caching, persistence) is wired
as placeholders and marked with `TODO (Milestone 2)` in the service layer.
