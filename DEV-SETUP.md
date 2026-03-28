# NourishAI Development Environment - Quick Setup Guide

This document provides multiple ways to quickly initialize your complete development environment.

## One-Command Setup

### Option 1: Using the Setup Script
```bash
./dev-setup.sh
```

### Option 2: Using Make
```bash
make setup
```

### Option 3: Using VS Code Tasks
1. Open Command Palette (`Cmd+Shift+P`)
2. Type "Tasks: Run Task"
3. Select "Setup Dev Environment"

## What Gets Started

- **Virtual Environment**: Python 3.9.6 activated
- **PostgreSQL**: Running on port 5432 (with pgvector)
- **Redis**: Running on port 6379  
- **FastAPI Server**: Running on http://127.0.0.1:8000

## Available VS Code Tasks

Access via `Cmd+Shift+P` → "Tasks: Run Task":

| Task | Description |
|------|-------------|
| Setup Dev Environment | Complete initialization |
| Start Docker Services | Start PostgreSQL + Redis |
| Stop Docker Services | Stop all Docker services |
| Activate Virtual Environment | Activate Python venv |
| Start API Server | Start FastAPI with auto-reload |
| Check Service Status | View running services |
| View Service Logs | Monitor service logs |
| Database Shell | Open PostgreSQL shell |
| Redis Shell | Open Redis CLI |

## VS Code Debug Configurations

Available via `F5` or Debug panel:

- **Debug FastAPI Server**: Debug with breakpoints
- **Run FastAPI with Uvicorn**: Run with debugging support

## Quick Access URLs

- **API Server**: http://127.0.0.1:8000
- **API Documentation**: http://127.0.0.1:8000/docs
- **ReDoc**: http://127.0.0.1:8000/redoc

## Manual Commands

If you prefer running commands manually:

```bash
# Activate virtual environment
source .venv/bin/activate

# Start Docker services
make up

# Start API server
./start-api.sh

# Check service status
make ps

# View logs
make logs

# Stop services
make down
```

## Troubleshooting

### Docker Not Running
```bash
open -a Docker
# Wait for Docker to start, then run setup again
```

### Virtual Environment Issues
```bash
rm -rf .venv
python3 -m venv .venv
source .venv/bin/activate
```

### Port Conflicts
```bash
# Check what's using ports
lsof -i :5432  # PostgreSQL
lsof -i :6379  # Redis
lsof -i :8000  # FastAPI
```

## Summary

Your development environment should now be fully operational. Happy coding!
