.PHONY: help install clean build package package-mac package-win package-linux package-all test lint

help:
	@echo "AI Document Assistant - Build Commands"
	@echo ""
	@echo "Available targets:"
	@echo "  install        - Install all dependencies (frontend & backend)"
	@echo "  clean          - Clean all build artifacts"
	@echo "  clean-release  - Clean release artifacts only"
	@echo "  build          - Build frontend and backend"
	@echo "  test           - Run all tests"
	@echo "  lint           - Run linters and type checks"
	@echo "  package-mac    - Package for macOS (dmg & zip)"
	@echo "  package-win    - Package for Windows (nsis & zip)"
	@echo "  package-linux  - Package for Linux (AppImage & deb)"
	@echo "  package-all    - Package for all platforms"
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
	rm -rf frontend/release
	rm -rf backend/.venv
	rm -rf backend/__pycache__
	rm -rf backend/**/__pycache__
	rm -rf backend/.pytest_cache
	rm -rf backend/htmlcov
	rm -rf backend/.coverage

clean-release:
	@echo "🧹 Cleaning release artifacts only..."
	rm -rf frontend/release
	rm -rf backend/dist

build: build-frontend build-backend

build-frontend:
	@echo "🔨 Building frontend..."
	cd frontend && npm run build

build-backend:
	@echo "🔨 Building backend executable..."
	cd backend && uv sync --dev
	cd backend && uv run pyinstaller build.spec --clean --noconfirm

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

package-mac: install build
	@echo "📦 Packaging for macOS..."
	cd frontend && npm run package -- --mac

package-win: install build
	@echo "📦 Packaging for Windows..."
	cd frontend && npm run package -- --win

package-linux: install build
	@echo "📦 Packaging for Linux..."
	cd frontend && npm run package -- --linux

package-all: install build
	@echo "📦 Packaging for all platforms..."
	cd frontend && npm run package -- -mwl

dev:
	@echo "🚀 Starting development servers..."
	@echo "Make sure Docker (Chroma) is running: docker-compose up -d"
	cd frontend && npm run dev