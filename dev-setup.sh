#!/bin/bash

# NourishAI Development Environment Setup Script
# This script initializes the complete development environment

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Project directory
PROJECT_DIR="/Applications/NourishAI/nourish_ai"

echo -e "${BLUE}🚀 NourishAI Development Environment Setup${NC}"
echo "================================================"

# Check if we're in the right directory
if [ "$(pwd)" != "$PROJECT_DIR" ]; then
    echo -e "${YELLOW}📁 Changing to project directory...${NC}"
    cd "$PROJECT_DIR"
fi

# Step 1: Check Docker
echo -e "${BLUE}🐳 Checking Docker...${NC}"
if ! docker info > /dev/null 2>&1; then
    echo -e "${RED}❌ Docker is not running. Please start Docker Desktop first.${NC}"
    echo -e "${YELLOW}💡 Opening Docker Desktop...${NC}"
    open -a Docker
    echo -e "${YELLOW}⏳ Waiting for Docker to start (30 seconds)...${NC}"
    sleep 30
    
    # Check again
    if ! docker info > /dev/null 2>&1; then
        echo -e "${RED}❌ Docker still not available. Please start Docker manually and run this script again.${NC}"
        exit 1
    fi
fi
echo -e "${GREEN}✅ Docker is running${NC}"

# Step 2: Check and create virtual environment
echo -e "${BLUE}🐍 Setting up Python virtual environment...${NC}"
if [ ! -d ".venv" ]; then
    echo -e "${YELLOW}📦 Creating virtual environment...${NC}"
    python3 -m venv .venv
fi

# Activate virtual environment
echo -e "${YELLOW}⚡ Activating virtual environment...${NC}"
source .venv/bin/activate

# Verify Python version
PYTHON_VERSION=$(python --version 2>&1)
echo -e "${GREEN}✅ Virtual environment active: ${PYTHON_VERSION}${NC}"

# Step 3: Install backend dependencies
echo -e "${BLUE}📚 Installing backend dependencies...${NC}"
cd backend
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
else
    echo -e "${YELLOW}📦 Installing core dependencies...${NC}"
    pip install uvicorn fastapi sqlalchemy psycopg2-binary redis pydantic-settings
fi
cd ..

# Step 4: Start Docker services
echo -e "${BLUE}🔧 Starting Docker services...${NC}"
make up

# Wait for services to be healthy
echo -e "${YELLOW}⏳ Waiting for services to be ready...${NC}"
sleep 5

# Check service status
echo -e "${BLUE}📊 Checking service status...${NC}"
make ps

# Step 5: Run database setup if needed
if [ -f "db-setup.sh" ]; then
    echo -e "${BLUE}🗄️  Setting up database...${NC}"
    ./db-setup.sh
fi

# Step 6: Start the API server in background
echo -e "${BLUE}🚀 Starting FastAPI server...${NC}"
echo -e "${YELLOW}💡 Starting server in background. Use 'make logs' to view logs.${NC}"

# Create a new terminal session for the API server
osascript -e "
tell application \"Terminal\"
    do script \"cd '$PROJECT_DIR' && source .venv/bin/activate && ./start-api.sh\"
end tell
"

# Summary
echo ""
echo -e "${GREEN}🎉 Development environment is ready!${NC}"
echo "================================================"
echo -e "${GREEN}✅ Virtual Environment:${NC} Activated (${PYTHON_VERSION})"
echo -e "${GREEN}✅ PostgreSQL:${NC} Running on port 5432"
echo -e "${GREEN}✅ Redis:${NC} Running on port 6379"
echo -e "${GREEN}✅ FastAPI Server:${NC} Starting on http://127.0.0.1:8000"
echo ""
echo -e "${BLUE}🔗 Quick Links:${NC}"
echo "• API Server: http://127.0.0.1:8000"
echo "• API Docs: http://127.0.0.1:8000/docs"
echo "• Redoc: http://127.0.0.1:8000/redoc"
echo ""
echo -e "${BLUE}📝 Useful Commands:${NC}"
echo "• Check services: make ps"
echo "• View logs: make logs"
echo "• Stop services: make down"
echo "• Database shell: make psql"
echo "• Redis shell: make redis"
echo ""
echo -e "${GREEN}🚀 Happy coding!${NC}"
