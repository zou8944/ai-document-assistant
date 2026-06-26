# AI Document Assistant

[简体中文](./README.md) | English

> **Vibe Coding Project** — This project was primarily built with AI-assisted programming (Claude Code). Code was AI-generated and human-reviewed.

An AI-powered document reading assistant built with React + Python. Supports local file processing, website content crawling, and intelligent Q&A based on RAG.

## Features

- Multi-format support: PDF, Word, Markdown, plain text, and more
- Recursive crawling of pages under the same domain
- RAG-powered Q&A with source citations
- One-command Docker Compose deployment

## Tech Stack

| Layer | Technology |
|-------|------------|
| Frontend | React + TypeScript + Tailwind CSS, served by Nginx |
| Backend | FastAPI + LangChain + Crawl4AI |
| Database | PostgreSQL (metadata) + ChromaDB (vectors) |
| Deployment | Docker Compose |

## Project Structure

```
ai-document-assistant/
├── backend/                 # Python backend
│   ├── api/                 # FastAPI routes
│   ├── crawler/             # Web crawling
│   ├── data_processing/     # File reading & text splitting
│   ├── database/            # ORM models, connection, migrations
│   ├── models/              # Pydantic models, DTOs
│   ├── rag/                 # RAG core logic
│   ├── repository/          # Data access layer
│   ├── services/            # Business logic layer
│   ├── vector_store/        # ChromaDB client
│   ├── api_server.py        # Entry point
│   └── .env.example         # Backend env template
├── frontend/                # React frontend
│   ├── src/
│   ├── nginx.conf
│   └── .env.example         # Frontend env template
├── docker-compose.yml
└── docker-compose.prod.yml
```

## Quick Start (Docker)

```bash
# 1. Configure AI environment variables
cp .env.deploy.example .env.deploy
# Edit .env.deploy — at minimum fill in CRAWL_API_KEY and AGENT_API_KEY

# 2. Deploy
make deploy-local

# 3. Open the app
open http://ai-assist.zou8944.com
```

On first deploy, `ai-assist.zou8944.com` is automatically added to `/etc/hosts`. You can change the domain and port in [frontend/nginx.conf](frontend/nginx.conf) and [docker-compose.yml](docker-compose.yml).

Service Ports:

| Service | Port | Notes |
|---------|------|-------|
| Frontend | 80 | Accessible via Nginx |
| Backend API | 18888 | Internal, not exposed externally |
| ChromaDB | 18000 | For external access if needed |
| PostgreSQL | 15432 | For external access if needed |

## Local Development

### Prerequisites

| Dependency | Version | Purpose |
|------------|---------|---------|
| Docker & Docker Compose | - | Run PostgreSQL and ChromaDB |
| Python | >= 3.9 | Backend runtime |
| [uv](https://docs.astral.sh/uv/) | - | Python dependency manager (replaces pip) |
| Node.js | >= 18 | Frontend build & dev server |
| npm | - | Frontend package manager (ships with Node.js) |

### Step 1: Start Infrastructure Services

```bash
docker compose up postgres chroma -d
```

Verify they're running:

```bash
docker compose ps
# Should see postgres (healthy) and chroma containers
```

### Step 2: Configure the Backend

```bash
cd backend
cp .env.example .env
```

Edit `.env` and fill in the required values:

```env
# Crawl LLM (any OpenAI-compatible API, e.g. SiliconFlow)
CRAWL_API_KEY=your_api_key_here
CRAWL_BASE_URL=https://api.siliconflow.cn/v1
CRAWL_MODEL=gpt-4o

# Chat Agent LLM (Anthropic Claude)
AGENT_API_KEY=your_anthropic_api_key_here
AGENT_MODEL=claude-sonnet-4-20250514

# Embedding model (OpenAI-compatible)
EMBEDDING_API_KEY=your_api_key_here
EMBEDDING_BASE_URL=https://api.openai.com/v1
EMBEDDING_MODEL=text-embedding-ada-002
```

Keep the database and Chroma connection settings at their defaults (pointing to `localhost`).

### Step 3: Install Dependencies & Start Backend

```bash
cd backend
uv sync                           # Install Python dependencies
uv run python api_server.py       # Start backend on port 8888
```

Verify: `curl http://localhost:8888/api/v1/health` should return a healthy response.

### Step 4: Start Frontend

In a separate terminal:

```bash
cd frontend
npm install          # Install frontend dependencies
npm run dev          # Start Vite dev server
```

Open `http://localhost:5173` in your browser.

### One-Command Start (macOS)

```bash
make dev
```

Opens the backend in a new terminal window and starts the frontend in the current one. First-time use requires granting Automation permission to your terminal app.

### Makefile Commands

| Command | Description |
|---------|-------------|
| `make install` | Install all frontend & backend dependencies |
| `make dev` | Start local dev environment (one command) |
| `make dev-backend` | Start backend only |
| `make dev-frontend` | Start frontend only |
| `make test` | Run all tests |
| `make lint` | Run linters (ruff + black + tsc) |
| `make migrate` | Run database migrations |

## Environment Variables

### Deployment (Docker)

Deployment config lives in `.env.deploy` at the project root. Template: [.env.deploy.example](.env.deploy.example). **AI config only** — database and Chroma settings are hardcoded in docker-compose.yml.

| Variable | Required | Description |
|----------|----------|-------------|
| `CRAWL_API_KEY` | Yes | Crawl-stage LLM API Key |
| `CRAWL_BASE_URL` | Yes | Crawl-stage API Base URL |
| `AGENT_API_KEY` | Yes | Chat Agent LLM API Key (Anthropic) |
| `EMBEDDING_API_KEY` | Yes | Embedding API Key |
| `EMBEDDING_BASE_URL` | Yes | Embedding API Base URL |
| `LOG_LEVEL` | No | Default `info` |

### Local Development

See [backend/.env.example](backend/.env.example). Includes database connection settings in addition to the AI config above.

| Variable | Description |
|----------|-------------|
| `POSTGRES_HOST` | Use `localhost` for local dev |
| `POSTGRES_PORT` | Default `5432` |
| `POSTGRES_USER` | Default `postgres` |
| `POSTGRES_PASSWORD` | Default `postgres` |
| `POSTGRES_DB` | Default `ai_document_assistant` |

## Docker Commands

```bash
# Service status
docker compose ps

# View logs
docker compose logs -f backend

# Restart a service
docker compose restart backend

# Rebuild and start
docker compose up -d --build

# Stop (preserves data volumes)
docker compose down

# Stop and delete all data
docker compose down -v
```

## Production Deployment

```bash
# With resource limits
make deploy-local
```

Or manually:

```bash
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

Notes:
- Set up HTTPS (recommend Traefik or Caddy as reverse proxy)
- Change the default database passwords in `docker-compose.yml`
- Back up data directory regularly (see below)

### Backup & Restore

All data is stored under `~/.ai-document-assistant/data/`:

```bash
# Backup everything
tar czf ~/ai-doc-backup.tar.gz ~/.ai-document-assistant/data/

# Restore
tar xzf ~/ai-doc-backup.tar.gz -C /

# Backup PostgreSQL only
docker compose exec postgres pg_dump -U postgres ai_document_assistant > backup.sql

# Restore PostgreSQL
cat backup.sql | docker compose exec -T postgres psql -U postgres ai_document_assistant
```

## Usage Guide

### Create a Collection
1. Go to "Collection Management" and click "Create New Collection"

### Upload Documents
1. Select a collection, click "Upload Documents"
2. Supports PDF, Word, Markdown, plain text, etc.
3. Wait for processing to complete (status becomes "indexed")

### Crawl a Website
1. Select a collection, click "Website Crawl"
2. Enter the start URL, set crawl scope
3. Wait for crawling to finish

### Q&A
1. Go to "Q&A", select a collection
2. Ask a question — answers include source references

## Debugging

See [DEBUG_GUIDE.md](DEBUG_GUIDE.md). VS Code debug configs are pre-set — press F5 and choose a configuration.

## Troubleshooting

**Port already in use**
```bash
lsof -i :80   # or :18888 / :18000 / :15432
# Update port mappings in docker-compose.yml
```

**Backend fails to start**
```bash
docker compose logs backend
curl http://localhost:18888/api/v1/health
```

**ChromaDB connection fails**
```bash
curl http://localhost:18000/api/v1/heartbeat
```

**Inaccurate Q&A results**
- Check Embedding model configuration
- Try adjusting `text.chunk_size` and `text.chunk_overlap`

## UI Design

Follows the Apple Liquid Glass style defined in [UI 设计指南.md](UI%20设计指南.md).

## License

MIT
