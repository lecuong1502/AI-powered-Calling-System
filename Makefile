.PHONY: help up down logs dev migrate test lint

help:
	@echo ""
	@echo "  AI Voice Call Platform — Dev Commands"
	@echo "  ────────────────────────────────────────────"
	@echo "  make up       Start all infra containers (PostgreSQL, MongoDB, Redis, Qdrant, MinIO)"
	@echo "  make down     Stop all containers"
	@echo "  make logs     Tail container logs"
	@echo "  make dev      Start FastAPI dev server (hot-reload)"
	@echo "  make migrate  Run Alembic migrations"
	@echo "  make test     Run pytest"
	@echo "  make lint     Run Ruff + mypy"
	@echo ""

# Infrastructure

up:
	docker compose -f infra/docker-compose.yml up -d
	@echo "✓ Infra up. Ports: PG=5432, Mongo=27017, Redis=6379, Qdrant=6333, MinIO=9000/9001"

down:
	docker compose -f infra/docker-compose.yml down

logs:
	docker compose -f infra/docker-compose.yml logs -f

# Backend

dev:
	cd backend && poetry run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

migrate:
	cd backend && poetry run alembic upgrade head

migrate-create:
	cd backend && poetry run alembic revision --autogenerate -m "$(MSG)"

test:
	cd backend && poetry run pytest -v --cov=app

lint:
	cd backend && poetry run ruff check . && poetry run mypy app --ignore-missing-imports

# Tunnel

tunnel:
	cloudflared tunnel --config infra/cloudflare/tunnel.yml run
