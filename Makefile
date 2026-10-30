# CloudLens developer shortcuts. Run `make help`.
.PHONY: help env up down restart logs ps build test test-backend test-frontend dev-backend dev-frontend lint backup screenshots clean

help:
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-16s %s\n", $$1, $$2}'

env: ## create .env from the template (once)
	@test -f .env && echo ".env already exists" || (cp .env.example .env && echo "created .env - edit secrets now")

up: ## build and start the full stack
	docker compose up -d --build

down: ## stop the stack (data volumes are kept)
	docker compose down

restart: ## restart backend + frontend
	docker compose restart backend frontend

logs: ## follow backend logs
	docker compose logs -f --tail=100 backend

ps: ## container status
	docker compose ps

test: test-backend test-frontend ## run all tests

test-backend: ## backend unit + API tests (SQLite in memory)
	cd backend && python -m pytest -q

test-backend-pg: ## backend tests against a PostgreSQL test database
	cd backend && TEST_DATABASE_URL=postgresql+psycopg://cloudlens:cloudlens@localhost:5432/cloudlens_test python -m pytest -q

test-frontend: ## frontend unit tests
	cd frontend && npm test

dev-backend: ## run the API locally with auto-reload (needs PostgreSQL)
	cd backend && ALERT_DELIVERY=direct uvicorn app.main:app --reload --port 8000

dev-frontend: ## run the React dev server on :5173
	cd frontend && npm run dev

lint: ## ruff for Python
	cd backend && ruff check app tests

backup: ## dump PostgreSQL to backups/
	./scripts/backup_db.sh

screenshots: ## capture screenshots of all screens into docs/screenshots
	python scripts/screenshots.py --base http://localhost:$${HTTP_PORT:-8080} --out docs/screenshots

clean: ## remove containers AND data volumes (destructive)
	docker compose down -v
