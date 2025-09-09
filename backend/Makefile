.PHONY: start-backend
start-backend:
	uv run --env-file ../.env uvicorn src.backend.main:app --host 0.0.0.0 --port 8000 --reload

.PHONY: health-check
health-check:
	@curl -f http://localhost:8000/health || echo "❌ Server not running"

.PHONY: format
format:
	uv run ruff format .

.PHONY: test-unit
test-unit:
	uv run pytest