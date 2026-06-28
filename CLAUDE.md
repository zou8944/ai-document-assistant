# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

AI Document Assistant — a RAG-based document Q&A tool. Users upload files or crawl websites into collections, then chat with an AI agent that retrieves and cites source documents. Built as a web app (React + FastAPI) that also runs as an Electron desktop app.

## Common Commands

### Local Development
```bash
# Start infrastructure (PostgreSQL + ChromaDB)
docker compose up postgres chroma -d

# Backend (from backend/)
uv sync
uv run python api_server.py               # starts on :8888

# Frontend (from frontend/)
npm install
npm run dev                                # starts on :5173, proxies /api to :8888

# One-command start (macOS, opens backend in new terminal)
make dev
```

### Docker Deployment
```bash
make deploy-local                          # builds and starts all containers
# Access at http://localhost:5174
# First launch: complete the setup wizard to configure API keys
```

### Testing
```bash
# Backend
cd backend && uv run pytest tests/ -v
uv run pytest tests/agent/test_runtime.py -v          # single file
uv run pytest tests/agent/test_runtime.py::test_name -v  # single test

# Frontend
cd frontend && npm test
npx vitest run src/components/chat/MarkdownContent.test.tsx  # single file
```

### Linting
```bash
# Backend (all from backend/)
uv run ruff check .
uv run black . --check
uv run mypy .

# Frontend (from frontend/)
npm run lint
npm run type-check

# All at once
make lint
```

### Database
```bash
# Migrations run automatically at backend startup
# Manual migration
cd backend && uv run alembic upgrade head

# Generate new migration after model changes
cd backend && uv run alembic revision --autogenerate -m "description"
```

## Architecture

### Data Flow

```
Frontend (React/Zustand)
    |  HTTP + SSE
    v
FastAPI routes (/api/v1/*)
    |  AppState injected at lifespan
    v
Service Layer
    |-- AgentChatService  <-- primary chat path (tool-use agent loop)
    |-- ChatService       <-- CRUD only, no response generation
    |-- TaskService       <-- background workers for ingestion
    |-- CollectionService, DocumentService, LLMService
    v
Repository Layer (SQLAlchemy)
    |-- PostgreSQL (metadata, settings, chat history)
    |-- ChromaDB  (vector embeddings, linked via DocumentChunk.vector_id)
```

### Chat Pipeline (Agent-based, production path)

The active chat path is in `backend/chat/agent/`. `AgentRuntime` runs an iterative tool-use loop:

1. Receives user query + conversation history + collection IDs
2. Calls LLM backend (`ClaudeToolBackend`, Anthropic only) with registered tools
3. LLM autonomously invokes tools (search, grep, get document, list collections, etc.)
4. Loop continues (up to 500 iterations) until LLM calls `StartAnswerTool`
5. `LoopDetector` prevents infinite loops; `Compaction` manages context window pressure
6. All events stream to frontend via SSE (`AGENT_START`, `TOOL_CALL`, `TOOL_RESULT`, `START_ANSWER`, etc.)

A legacy RAG pipeline exists in `backend/rag/` but is no longer used for chat responses.

### Key Backend Modules

| Path | Role |
|------|------|
| `api/main.py` | FastAPI app, lifespan (migrations, config, service init) |
| `api/state.py` | `AppState` dataclass holding all services |
| `api/routes/` | 8 route modules, all under `/api/v1` |
| `services/` | Business logic (LLM, tasks, collections, documents, chat) |
| `chat/agent/` | Agent runtime, tool registry, LLM backends |
| `chat/retrieval/` | Hybrid retrieval: vector + document + keyword indexes |
| `chat/context/` | Query expansion |
| `rag/` | Legacy RAG prompts and summarizer (still used by tasks) |
| `repository/` | SQLAlchemy data access |
| `database/models/` | ORM models |
| `database/migrations/` | Alembic migrations (auto-run at startup) |
| `vector_store/` | ChromaDB client (persistent local or HTTP) |
| `crawler/` | Web crawling |
| `data_processing/` | File reading, text splitting (LangChain RecursiveCharacterTextSplitter) |
| `config.py` | Config loading: env vars → TOML file → DB settings |
| `settings_util.py` | DB-backed settings with encryption for API keys |

### Key Frontend Modules

| Path | Role |
|------|------|
| `src/App.tsx` | Startup flow: health poll → config check → SetupWizard or MainLayout |
| `src/store/appStore.ts` | Zustand global state (persist + devtools) |
| `src/services/apiClient.ts` | Typed API client, `useAPIClient()` hook |
| `src/components/chat/` | Chat UI, agent trace, markdown rendering, tool renderers |
| `src/components/knowledge/` | Collection management, document viewer |
| `src/components/settings/SetupWizard.tsx` | First-launch API key configuration |

### Configuration

AI settings (API keys, models, URLs) are stored in the PostgreSQL `settings` table and managed through the frontend settings UI. Sensitive values are encrypted at rest.

On first launch, `settings_util.py` seeds default settings. The frontend checks `/api/v1/settings/status` and shows a setup wizard if critical keys are missing.

`config.py` loads config in priority order: DB settings > TOML file > env vars > defaults. Env vars (`DOCKER_ENV=true` triggers env-based bootstrap) are only used for the initial Docker startup before the DB is ready.

## Coding Conventions

### Backend (Python 3.9+)
- Package manager: `uv` (not pip). `uv sync` to install, `uv run` to execute.
- Use `list` not `typing.List`, `dict` not `typing.Dict`
- Absolute imports only, no relative imports
- No trailing whitespace on blank lines (ruff enforces this)
- Formatter: `black`, linter: `ruff`
- Run from `backend/` directory (it must be on PYTHONPATH)

### Frontend (TypeScript/React)
- State: Zustand with persist + devtools middleware
- Styling: Tailwind CSS, following `UI 设计指南.md` (Apple Liquid Glass style)
- Path aliases: `@/components`, `@/services`, `@/styles`

### Git
- Conventional Commits: `feat:` / `fix:` / `refactor:` / `chore:` / `docs:` / `infra:`
- Feature branches, merge to main via PR

### Documentation
- Requirements/design docs go in `requirements/` directory
- Naming: `{next_number} - {中文标题}.md` (check `ls requirements/` for next number)
- Do not place docs in project root or `~/.claude/plans/`

## Vibe Coding

This project is primarily built with AI-assisted programming (Claude Code). Code is AI-generated and human-reviewed.
