.PHONY: up down build logs ps psql migrate revision shell-backend restart

up:
	docker compose up -d --build

down:
	docker compose down

build:
	docker compose build

logs:
	docker compose logs -f --tail=200

ps:
	docker compose ps

psql:
	docker compose exec postgres psql -U $${POSTGRES_USER:-llmarena} -d $${POSTGRES_DB:-llmarena}

migrate:
	docker compose exec backend alembic upgrade head

revision:
	@if [ -z "$(name)" ]; then echo "usage: make revision name=description"; exit 1; fi
	docker compose exec backend alembic revision --autogenerate -m "$(name)"

shell-backend:
	docker compose exec backend /bin/sh

restart:
	docker compose restart backend
