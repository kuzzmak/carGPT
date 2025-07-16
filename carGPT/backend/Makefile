# Variables
APP_MODULE=main:app  # Change this to your app module (e.g., package.module:app)
HOST=0.0.0.0         # Host for uvicorn
PORT=8000            # Port for uvicorn

# Default target
.PHONY: start
start:
	deactivate && poetry shell && uvicorn $(APP_MODULE) --host $(HOST) --port $(PORT) --reload

# Target to start server without poetry shell
.PHONY: run
run:
	poetry run uvicorn $(APP_MODULE) --host $(HOST) --port $(PORT) --reload

# Install dependencies using Poetry
.PHONY: install
install:
	poetry install

# Format code with black
.PHONY: format
format:
	poetry run black .

# Lint code with flake8
.PHONY: lint
lint:
	poetry run flake8 .

# Run tests
.PHONY: test
test:
	poetry run pytest
