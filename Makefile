COMPOSE = docker compose

.PHONY: up down build restart logs ps shell-backend

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
