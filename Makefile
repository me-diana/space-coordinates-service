PROD_COMPOSE = docker compose -f docker-compose.yml
DEV_COMPOSE = docker compose -f docker-compose.yml -f docker-compose.dev.yml

.PHONY: build start up down dev-build dev-start dev-up dev-down test test-down

build:
	$(PROD_COMPOSE) build --no-cache

start:
	$(PROD_COMPOSE) up -d --remove-orphans

up: build start

down:
	$(PROD_COMPOSE) down

dev-build:
	$(DEV_COMPOSE) build --no-cache

dev-start:
	$(DEV_COMPOSE) up --remove-orphans

dev-up: dev-build dev-start

dev-down:
	$(DEV_COMPOSE) down


TEST_COMPOSE = docker compose -p space-coordinates-service-test -f docker-compose.yml -f docker-compose.dev.yml --env-file .env.test

test:
	poetry run pytest -m "not integration"
	$(TEST_COMPOSE) stop
	$(TEST_COMPOSE) up -d --wait postgres redis
	set -a && . ./.env.test && set +a && poetry run alembic upgrade head
	set -a && . ./.env.test && set +a && poetry run pytest -m integration
	$(TEST_COMPOSE) down

test-down:
	$(TEST_COMPOSE) down
