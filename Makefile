# Strong Start developer entry points (INIT-001 s8). Underlying commands are documented in
# docs/setup/README.md for systems without make. Run from the repository root.
SHELL := /bin/bash
.DEFAULT_GOAL := help
COMPOSE := docker compose -f infra/compose.yaml
UV := uv run
SCHEMA := packages/contracts/schema/strongstart-contracts.schema.json

.PHONY: help bootstrap browser-install db-up db-down migrate seed-demo dev-api dev-web \
        lint format typecheck test contracts contracts-check build smoke browser-smoke check tigerdata-smoke

help: ## List targets
	@grep -E '^[a-z-]+:.*## ' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-16s %s\n", $$1, $$2}'

bootstrap: ## Install locked Python + JS dependencies; create .env from .env.example if absent
	uv sync --locked
	npm ci
	@test -f .env || { cp .env.example .env; echo "created .env from .env.example"; }

browser-install: ## Download Playwright Chromium into the user cache (no system packages)
	$(UV) playwright install chromium

db-up: ## Start only the local development PostgreSQL service
	$(COMPOSE) up -d --wait postgres

db-down: ## Stop the local PostgreSQL service (data volume kept)
	$(COMPOSE) down

migrate: ## Apply the shared Alembic migration history
	$(UV) alembic upgrade head

seed-demo: ## Upsert synthetic demo metadata (idempotent; refuses production)
	$(UV) strongstart-seed-demo

dev-api: ## Run the API on 127.0.0.1:8000 with reload
	$(UV) uvicorn --factory strongstart_api.app:app_factory --host 127.0.0.1 --port 8000 --reload

dev-web: ## Run the web shell on 127.0.0.1:5173 (proxies /api and /health to :8000)
	npm run dev -w @strongstart/web

lint: ## Ruff + oxlint + format checks
	$(UV) ruff check .
	$(UV) ruff format --check .
	npm run lint
	npm run format:check

format: ## Apply formatters (ruff format, prettier)
	$(UV) ruff format .
	$(UV) ruff check --fix .
	npm run format

typecheck: ## mypy (strict) + TypeScript
	$(UV) mypy
	npm run typecheck

test: ## Default no-secret, no-network tests (pytest without db/browser markers, vitest)
	$(UV) pytest
	npm test

contracts: ## Regenerate JSON Schema and TypeScript declarations from Pydantic models
	$(UV) python -m strongstart_contracts.export $(SCHEMA)
	npm run contracts:generate

contracts-check: ## Fail if committed schema/TS declarations differ from a fresh generation
	@tmp=$$(mktemp) && $(UV) python -m strongstart_contracts.export $$tmp && \
	  if ! cmp -s $$tmp $(SCHEMA); then echo "contract drift: $(SCHEMA) is stale; run make contracts"; rm -f $$tmp; exit 1; fi; \
	  rm -f $$tmp; echo "contracts: JSON Schema matches the models"
	npm run contracts:check

build: ## Build the web app and Python wheels
	npm run build
	uv build --all-packages --out-dir dist/python

smoke: migrate seed-demo ## Imports, real API process health/readiness, DB migration/seed path
	$(UV) pytest -q tests/unit/test_imports.py
	$(UV) pytest -m db tests/smoke tests/skills
	$(UV) python scripts/smoke_server.py

browser-smoke: ## Build web, then Chromium browser tests (fixture read-back + Funding page e2e)
	npm run build
	$(UV) pytest -m browser -s tests/browser

check: lint typecheck test contracts-check build ## All no-DB checks

tigerdata-smoke: ## Explicit hosted gate; supply TIGERDATA_ARGS='--manifest private.json --phase preflight'
	$(UV) python -m scripts.tigerdata_smoke $(TIGERDATA_ARGS)
