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

# Create necessary directories
echo "Creating init scripts directory..."
mkdir -p db/init

# Copy seed files
echo "Copying seed files..."
cp backend/app/db/init/*.sql db/init/

# Stop existing containers and remove volumes
echo "Stopping existing containers and removing volumes..."
docker compose down -v

# Start fresh containers
echo "Starting fresh containers..."
docker compose up -d

# Wait for PostgreSQL to be ready
echo "Waiting for PostgreSQL to initialize..."
sleep 5

# Test database connection and show tables
echo "Testing database connection..."
docker exec -it pantryplate-postgres psql -U pantry -d pantrydb -c "\dt;"

# Show sample data
echo -e "\nShowing sample data from recipes table..."
docker exec -it pantryplate-postgres psql -U pantry -d pantrydb -c "SELECT * FROM recipes;"

echo -e "\nDatabase setup complete!"

# =============================================================================
# HOW TO USE THIS SCRIPT
# =============================================================================
#
# This script will:
# 1. Create necessary directories
# 2. Copy seed files to the correct location
# 3. Restart Docker containers with fresh volumes
# 4. Initialize the database with seed data
# 5. Show table structure and sample data
#
# To use:
# 1. Make sure you're in the project directory:
#    cd /Applications/NourishAI/nourish_ai
#
# 2. Run the script:
#    ./db-setup.sh
#
# Notes:
# - This script will remove existing data in the database
# - Use it mainly for development and testing
# - Add new seed files in backend/app/db/init/ with numeric prefixes
#   (e.g., 020_more_recipes.sql)
