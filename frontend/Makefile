.PHONY: start-frontend

start-frontend: ## Start the frontend development server
	uv run --env-file ../.env python -m streamlit run src/frontend/main.py --server.port 8501 --server.address localhost --browser.serverAddress localhost
