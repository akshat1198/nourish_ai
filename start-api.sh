#!/bin/bash

# Exit on any error
set -e

# Project directory
PROJECT_DIR="/Applications/NourishAI/nourish_ai"

# Check if we're in the right directory
if [ ! -d "$PROJECT_DIR" ]; then
    echo "Error: Project directory not found at $PROJECT_DIR"
    exit 1
fi

# Change to project directory
cd "$PROJECT_DIR"

# Check if virtual environment exists
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate virtual environment
if [ -f ".venv/bin/activate" ]; then
    source .venv/bin/activate
else
    echo "Error: Virtual environment activation script not found"
    exit 1
fi

# Install requirements if needed
if ! command -v uvicorn &> /dev/null; then
    echo "Installing dependencies..."
    pip install uvicorn fastapi sqlalchemy psycopg2-binary redis pydantic-settings
fi

# Check if backend directory exists
if [ ! -d "backend" ]; then
    echo "Error: backend directory not found"
    exit 1
fi

# Change to backend directory
cd backend

# Start the FastAPI server
echo "Starting FastAPI server..."
exec python3 -m uvicorn app.main:app --reload

# =============================================================================
# HOW TO USE THIS PROJECT
# =============================================================================
#
# Steps to run the application:
#
# 1. Navigate to the project directory:
#    cd /Applications/NourishAI/nourish_ai
#
# 2. Start Docker containers (if not already running):
#    docker compose up -d
#
# 3. Run this script:
#    ./start-api.sh
#
# 4. Test the health endpoint (in a new terminal):
#    curl http://localhost:8000/health
#    # Should return: {"db": true, "redis": true}
#
# Additional Makefile commands available:
#    make up      - Start containers
#    make ps      - Check container status
#    make logs    - View container logs
#    make psql    - Connect to PostgreSQL
#    make redis   - Connect to Redis
#    make down    - Stop containers
#
# Notes:
# - Press Ctrl+C to stop the server
# - Code changes will auto-reload
# - Restart server if you change dependencies or environment variables
# =============================================================================
