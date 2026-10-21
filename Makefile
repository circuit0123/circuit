.PHONY: up down migrate run test check reset-demo openapi lint
BACKEND = uv run --directory backend

up:
	docker compose up -d --wait

down:
	docker compose down

migrate:
	$(BACKEND) python manage.py migrate

run:
	$(BACKEND) python manage.py runserver 8000

reset-demo:
	$(BACKEND) python manage.py reset_demo

openapi:
	$(BACKEND) python manage.py export_openapi ../packages/api-client/openapi.json

lint:
	$(BACKEND) ruff check . && $(BACKEND) ruff format --check . && $(BACKEND) mypy .

test:
	$(BACKEND) pytest

check: lint
	$(BACKEND) pytest -p no:cacheprovider
