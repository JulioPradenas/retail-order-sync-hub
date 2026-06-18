.DEFAULT_GOAL := help
SHELL := /bin/bash

# Compose files (skeletons in phase 0; real services land in later phases)
COMPOSE      := docker compose -f infra/docker-compose.yml
COMPOSE_OBS  := docker compose -f infra/docker-compose.obs.yml

.PHONY: help fix check test up down logs migrate seed obs-up obs-down dbt-run dbt-test dbt-docs

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

fix: ## Auto-fix: ruff format + ruff check --fix + mypy + pytest (pre-commit standard)
	uv run ruff format .
	uv run ruff check --fix .
	uv run mypy
	uv run pytest

check: ## CI gate: ruff check + mypy + pytest (no auto-fix)
	uv run ruff format --check .
	uv run ruff check .
	uv run mypy
	uv run pytest

test: ## Run pytest with coverage
	uv run pytest

up: ## Start the local stack
	$(COMPOSE) up -d

down: ## Stop the local stack
	$(COMPOSE) down

logs: ## Tail logs of the local stack
	$(COMPOSE) logs -f

migrate: ## Apply Alembic migrations to app_db
	uv run alembic upgrade head

obs-up: ## Start the observability stack (Grafana/Prometheus/Tempo)
	$(COMPOSE_OBS) up -d

obs-down: ## Stop the observability stack
	$(COMPOSE_OBS) down

seed: ## Seed Odoo with reproducible demo data
	uv run python -m scripts.seed_odoo

dbt-run: ## Run dbt models
	cd dbt && uv run dbt run

dbt-test: ## Run dbt tests
	cd dbt && uv run dbt test

dbt-docs: ## Generate dbt docs
	cd dbt && uv run dbt docs generate
