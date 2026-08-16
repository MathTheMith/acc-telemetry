COMPOSE = docker compose

.PHONY: up down build restart logs ps shell-backend backup restore seed reset

up: ## Build (if needed) and start the whole stack in the background
	$(COMPOSE) up --build -d

down: ## Stop and remove the containers
	$(COMPOSE) down

build: ## Rebuild the images without starting them
	$(COMPOSE) build

restart: down up ## Restart the whole stack

logs: ## Show logs for all services (Ctrl+C to quit)
	$(COMPOSE) logs -f

ps: ## List container status
	$(COMPOSE) ps

shell-backend: ## Open a shell in the backend container
	$(COMPOSE) exec backend sh

backup: ## Back up the SQLite database into backups/ (keeps the last 14)
	./scripts/backup.sh

restore: ## Restore the database from a file: make restore FILE=backups/telemetry-xxx.db
	@test -n "$(FILE)" || (echo "Usage: make restore FILE=backups/telemetry-xxx.db" && exit 1)
	$(COMPOSE) cp $(FILE) backend:/data/telemetry.db
	$(COMPOSE) restart backend

seed: ## Insert a few demo laps (simulator) to test the site without ACC
	python3 scripts/seed_demo.py

reset: ## Remove everything (containers + volume, including the DB) then restart
	$(COMPOSE) down -v
	$(COMPOSE) up --build -d
