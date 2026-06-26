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
# 1. Deploy
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build

# 2. Open the app
open http://localhost
# On first launch, complete the setup wizard in the browser
```

Service Ports:

| Service | Port | Notes |
|---------|------|-------|
| Frontend | 5174 | App entry point, served by Nginx |
| Backend API | 51741 | For debugging only; normal access goes through frontend proxy |

> PostgreSQL and ChromaDB are only exposed within the Docker internal network, not on the host. The backend connects to them via service names `postgres` / `chroma`.

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

Only database connection settings are needed in `.env` (defaults work for local dev). AI configuration (Crawl / Agent / Embedding) is managed through the **frontend settings UI** after the backend starts, stored in the database.

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

### AI Configuration (via Frontend Settings UI)

All AI-related settings (Crawl / Agent / Embedding API keys, models, URLs) are managed through the **frontend settings interface** and stored in the database. No manual env var editing needed.

### Deployment (Docker)

Database and Chroma settings are hardcoded in docker-compose.yml. AI configuration is completed through the frontend settings UI. Just run the setup wizard in the browser after first launch.

### Local Development

Only database connection settings are needed in [backend/.env](backend/.env):

| Variable | Default | Description |
|----------|---------|-------------|
| `POSTGRES_HOST` | `localhost` | PostgreSQL host |
| `POSTGRES_PORT` | `5432` | PostgreSQL port |
| `POSTGRES_USER` | `postgres` | Database user |
| `POSTGRES_PASSWORD` | `postgres` | Database password |
| `POSTGRES_DB` | `ai_document_assistant` | Database name |

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
lsof -i :5174   # or :51741
# Update port mappings in docker-compose.yml
```

**Backend fails to start**
```bash
docker compose logs backend
curl http://localhost:51741/api/v1/health
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
