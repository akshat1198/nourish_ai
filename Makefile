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
