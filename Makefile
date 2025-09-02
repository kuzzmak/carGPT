# CarGPT Backend Docker Management
# This Makefile provides convenient commands for managing the Docker Compose setup

# Default environment
ENV ?= dev
COMPOSE_CMD = docker compose

.PHONY: help build up down restart logs shell test clean

# Default target
help: ## Show this help message
	@echo "CarGPT Backend Docker Management"
	@echo "================================"
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ { printf "  %-15s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)

build: ## Build the backend Docker image
	$(COMPOSE_CMD) build --no-cache

up: ## Start all services in development mode
	$(COMPOSE_CMD) up -d
	@echo "🚀 Services started!"
	@echo "📝 Backend API: http://localhost:8000"
	@echo "📊 API Docs: http://localhost:8000/docs"

up-prod: ## Start all services in production mode
	$(COMPOSE_CMD) -f docker-compose.yml -f docker-compose.prod.yml up -d
	@echo "🚀 Production services started!"

up-tools: ## Start services with PgAdmin
	$(COMPOSE_CMD) --profile tools up -d
	@echo "🚀 Services with tools started!"
	@echo "📝 Backend API: http://localhost:8000"
	@echo "🗄️  PgAdmin: http://localhost:5050"

up-db: ## Start only the database service
	$(COMPOSE_CMD) up -d postgres
	@echo "🗄️  Database started!"
	@echo "📊 PostgreSQL: localhost:5432"

down: ## Stop all services
	$(COMPOSE_CMD) down --remove-orphans
	@echo "🛑 Services stopped"

down-volumes: ## Stop all services and remove volumes (⚠️  deletes data!)
	$(COMPOSE_CMD) down -v
	@echo "🛑 Services stopped and volumes removed"

restart: ## Restart all services
	$(COMPOSE_CMD) restart
	@echo "🔄 Services restarted"

logs: ## Show logs from all services
	$(COMPOSE_CMD) logs -f

logs-backend: ## Show logs from backend service only
	$(COMPOSE_CMD) logs -f backend

logs-db: ## Show logs from database service only
	$(COMPOSE_CMD) logs -f postgres

shell: ## Open shell in backend container
	$(COMPOSE_CMD) exec backend bash

shell-db: ## Open PostgreSQL shell
	$(COMPOSE_CMD) exec postgres psql -U adsuser -d ads_db

test: ## Run API tests against running containers
	@echo "🧪 Testing API endpoints..."
	@$(COMPOSE_CMD) exec backend uv run python test_api.py || echo "⚠️  Make sure containers are running with 'make up'"

status: ## Show status of all services
	$(COMPOSE_CMD) ps

clean: ## Remove unused Docker resources
	docker system prune -f
	docker volume prune -f
	@echo "🧹 Docker cleanup completed"

rebuild: ## Rebuild and restart all services
	$(COMPOSE_CMD) down
	$(COMPOSE_CMD) build --no-cache
	$(COMPOSE_CMD) up -d
	@echo "🔄 Services rebuilt and restarted"

# Development helpers
dev-setup: build up ## Complete development setup (build and start)
	@echo "✅ Development environment ready!"
	@echo "📝 API Documentation: http://localhost:8000/docs"

# Production helpers
prod-deploy: ## Deploy in production mode
	$(COMPOSE_CMD) -f docker-compose.yml -f docker-compose.prod.yml up -d --build
	@echo "🚀 Production deployment complete!"

# Database helpers
db-backup: ## Create database backup
	@mkdir -p backups
	$(COMPOSE_CMD) exec postgres pg_dump -U adsuser ads_db > backups/ads_db_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "💾 Database backup created in backups/ directory"

db-restore: ## Restore database from backup (requires BACKUP_FILE=path)
	@if [ -z "$(BACKUP_FILE)" ]; then echo "❌ Please specify BACKUP_FILE=path"; exit 1; fi
	$(COMPOSE_CMD) exec -T postgres psql -U adsuser ads_db < $(BACKUP_FILE)
	@echo "📥 Database restored from $(BACKUP_FILE)"

# FastAPI server commands
.PHONY: run run-dev run-prod

# Start FastAPI server in development mode
run: ## Start FastAPI server with auto-reload
	uv run uvicorn src.backend.main:app --host 0.0.0.0 --port 8000 --reload

# Alternative development server command
run-dev: ## Start FastAPI development server
	uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload --log-level debug

# Start FastAPI server in production mode
run-prod: ## Start FastAPI server in production mode
	uv run uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4

# Quick server start using the start_server.sh script
quick-start: ## Quick start using start_server.sh script
	./start_server.sh

# Check API health
health-check: ## Check if the API server is running
	@curl -f http://localhost:8000/health || echo "❌ Server not running"

# Open API documentation in browser
docs: ## Open API documentation in default browser
	@echo "📝 Opening API docs at http://localhost:8000/docs"
	@python -m webbrowser http://localhost:8000/docs || echo "Please open http://localhost:8000/docs manually"

# Install dependencies using uv
.PHONY: install sync
install: ## Install dependencies using uv
	uv sync

sync: ## Sync dependencies using uv (alias for install)
	uv sync

# Format code with ruff
.PHONY: format
format:
	uv run ruff format .

# Run tests with pytest
.PHONY: test-unit
test-unit: ## Run unit tests with pytest
	uv run pytest
