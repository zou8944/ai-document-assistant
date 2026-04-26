.PHONY: help install clean build test lint dev dev-frontend dev-backend migrate

help:
	@echo "AI Document Assistant - Build Commands"
	@echo ""
	@echo "Available targets:"
	@echo "  install        - Install all dependencies (frontend & backend)"
	@echo "  clean          - Clean all build artifacts"
	@echo "  build          - Build frontend for production"
	@echo "  test           - Run all tests"
	@echo "  lint           - Run linters and type checks"
	@echo "  dev            - Start backend (new Terminal) + frontend (current Terminal)"
	@echo "  dev-backend    - Start backend dev server"
	@echo "  dev-frontend   - Start frontend dev server"
	@echo "  migrate        - Run database migrations (alembic upgrade head)"
	@echo ""

install: install-frontend install-backend

install-frontend:
	@echo "📦 Installing frontend dependencies..."
	cd frontend && npm install

install-backend:
	@echo "🐍 Installing backend dependencies..."
	cd backend && uv sync

clean:
	@echo "🧹 Cleaning build artifacts..."
	rm -rf frontend/dist
	rm -rf backend/__pycache__
	rm -rf backend/**/__pycache__
	rm -rf backend/.pytest_cache
	rm -rf backend/htmlcov
	rm -rf backend/.coverage

build: build-frontend

build-frontend:
	@echo "🔨 Building frontend..."
	cd frontend && npm run build

test: test-frontend test-backend

test-frontend:
	@echo "🧪 Running frontend tests..."
	cd frontend && npm test

test-backend:
	@echo "🧪 Running backend tests..."
	cd backend && uv run pytest tests/ -v

lint: lint-frontend lint-backend

lint-frontend:
	@echo "🔍 Linting frontend..."
	cd frontend && npm run lint
	cd frontend && npm run type-check

lint-backend:
	@echo "🔍 Linting backend..."
	cd backend && uv run ruff check .
	cd backend && uv run black . --check
	cd backend && uv run mypy .

migrate:
	@echo "🗄️  Running database migrations..."
	cd backend && uv run alembic upgrade head

dev-backend:
	@echo "🚀 Starting backend server..."
	cd backend && exec uv run python api_server.py

dev-frontend:
	@echo "🚀 Starting frontend dev server..."
	cd frontend && exec npm run dev

dev:
	@echo "🚀 Starting development servers in separate terminals..."
	@echo "Make sure Docker (Chroma) is running: docker compose up -d"
	@osascript -e 'tell application "Terminal" to do script "cd $(CURDIR)/backend && uv run python api_server.py"' >/dev/null 2>&1; \
	OSACODE=$$?; \
	if [ $$OSACODE -ne 0 ]; then \
		echo ""; \
		echo "⚠️  Cannot open a new Terminal window automatically."; \
		echo ""; \
		echo "   This is usually a macOS permission issue. Either:"; \
		echo ""; \
		echo "   Option A - Grant permission (one-time):"; \
		echo "     1. Open System Settings > Privacy & Security > Automation"; \
		echo "     2. Find your terminal app and enable 'Terminal' under it"; \
		echo ""; \
		echo "   Option B - Start manually in two terminals:"; \
		echo "     Terminal 1: make dev-backend"; \
		echo "     Terminal 2: make dev-frontend"; \
		echo ""; \
		exit 1; \
	fi
	@sleep 2
	cd frontend && npm run dev
