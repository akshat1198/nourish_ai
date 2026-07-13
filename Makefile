setup:
	@./dev-setup.sh

api:
	@cd backend && ../.venv/bin/uvicorn app.main:app --reload

test:
	@cd backend && ../.venv/bin/pytest

migrate:
	@cd backend && ../.venv/bin/alembic upgrade head

revision:
	@cd backend && ../.venv/bin/alembic revision -m "$(m)"

up:
	@docker compose up -d

down:
	@docker compose down

logs:
	@docker compose logs -f

ps:
	@docker compose ps

psql:
	@docker exec -it pantryplate-postgres psql -U pantry -d pantrydb

redis:
	@docker exec -it pantryplate-redis redis-cli

# MCP server (Stage 4.1) — separate image (no FastAPI), spawned by MCP clients.
mcp-build:
	@docker build -f backend/Dockerfile.mcp -t nourish-mcp backend

mcp-verify:
	@docker run --rm --network nourish_ai_default \
		-e DATABASE_URL='postgresql+psycopg2://pantry:pantrypw@db:5432/pantrydb' \
		nourish-mcp python scripts/verify_mcp.py
