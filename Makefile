# Tata AI Software Factory — task runner. All targets delegate to scripts/.
# Override flags:  make start ARGS="--dry-run --verbose"
SHELL := /usr/bin/env bash
S     := ./scripts
ARGS  ?=

.DEFAULT_GOAL := help
.PHONY: help install setup bootstrap dev start stop restart status logs health \
        build test lint format migrate seed deploy update backup restore \
        clean reset check-env

help: ## Show this help
	@grep -hE '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  \033[36m%-12s\033[0m %s\n",$$1,$$2}'

install: ## Install OS prerequisites (Ubuntu/apt)
	@$(S)/install.sh $(ARGS)
setup: ## Create venv + install app/extension deps
	@$(S)/setup.sh $(ARGS)
bootstrap: ## Fresh setup: deps -> env -> migrate -> seed
	@$(S)/bootstrap.sh $(ARGS)
check-env: ## Validate required environment variables
	@$(S)/check-env.sh $(ARGS)

dev: ## Run dashboard with reload
	@$(S)/dev.sh $(ARGS)
start: ## Start all services
	@$(S)/start.sh $(ARGS)
stop: ## Stop all services
	@$(S)/stop.sh $(ARGS)
restart: ## Restart all services
	@$(S)/restart.sh $(ARGS)
status: ## Show service status
	@$(S)/status.sh $(ARGS)
logs: ## Tail logs
	@$(S)/logs.sh $(ARGS)
health: ## Health-check all services
	@$(S)/health.sh $(ARGS)

build: ## Build images/packages
	@$(S)/build.sh $(ARGS)
test: ## Run test suite
	@$(S)/test.sh $(ARGS)
lint: ## Run linters
	@$(S)/lint.sh $(ARGS)
format: ## Auto-format code
	@$(S)/format.sh $(ARGS)
migrate: ## Apply DB migrations
	@$(S)/migrate.sh $(ARGS)
seed: ## Seed the database
	@$(S)/seed.sh $(ARGS)

deploy: ## Deploy (prod compose)
	@$(S)/deploy.sh $(ARGS)
update: ## Pull + rebuild + migrate + restart
	@$(S)/update.sh $(ARGS)
backup: ## Backup database/volumes
	@$(S)/backup.sh $(ARGS)
restore: ## Restore from backup
	@$(S)/restore.sh $(ARGS)
clean: ## Remove build artifacts/caches
	@$(S)/clean.sh $(ARGS)
reset: ## Full clean + fresh bootstrap
	@$(S)/reset.sh $(ARGS)
