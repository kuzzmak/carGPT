# frontend/Dockerfile
FROM python:3.10-slim

# Set environment variables for Poetry
ENV POETRY_VERSION=1.8.3 \
    POETRY_VIRTUALENVS_CREATE=false \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# Install Poetry
RUN pip install --no-cache-dir poetry==$POETRY_VERSION

# Set the working directory
WORKDIR /app

# Copy only the necessary files to install dependencies
COPY pyproject.toml poetry.lock /app/

# Install dependencies
RUN poetry install --no-root

# Copy the application code
COPY . /app

# Set the BACKEND_URL environment variable
ENV BACKEND_URL=http://backend:8000

# Expose the port the app runs on
EXPOSE 8501

# Run the application
CMD ["streamlit", "run", "app.py", "--server.address=0.0.0.0"]
