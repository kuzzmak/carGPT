#!/bin/bash

# CarGPT Backend Startup Script
# This script installs dependencies and starts the FastAPI server

set -e

echo "🚀 Starting CarGPT Backend Setup..."

# Check if we're in the correct directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: pyproject.toml not found. Please run this script from the backend directory."
    exit 1
fi

# Install dependencies using uv
echo "📦 Installing dependencies with uv..."
uv sync

echo "✅ Dependencies installed successfully!"

# Start the FastAPI server using uv
echo "🌟 Starting FastAPI server..."
echo "📝 API Documentation will be available at: http://localhost:8000/docs"
echo "📋 ReDoc documentation at: http://localhost:8000/redoc"
echo "💡 Press Ctrl+C to stop the server"

uv run uvicorn main:app --host 0.0.0.0 --port 8000 --reload
