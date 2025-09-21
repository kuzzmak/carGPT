.PHONY: start-db-server health-check format test-unit

start-db-server: ## Start the MCP database server
	uv run --env-file ../.env python src/mcp_servers/database/server.py

health-check: ## Check if the MCP database server is running
	@echo "🔍 Checking MCP database server health..."
	@curl -f http://localhost:$${ADS_DB_MCP_SERVER_PORT:-8001}/health 2>/dev/null || echo "❌ MCP database server not running on port $${ADS_DB_MCP_SERVER_PORT:-8001}"

format: ## Format code using ruff
	uv run ruff format .

test-unit: ## Run unit tests
	uv run pytest

help: ## Show this help message
	@echo "MCP Servers Management"
	@echo "====================="
	@echo "Available commands:"
	@awk 'BEGIN {FS = ":.*##"} /^[a-zA-Z_-]+:.*##/ { printf "  %-15s %s\n", $$1, $$2 }' $(MAKEFILE_LIST)
