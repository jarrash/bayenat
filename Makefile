setup:
	cp -n .env.example .env || true
	python3 -m venv .venv
	. .venv/bin/activate && pip install -r backend/requirements.txt

dev:
	docker compose -f infrastructure/docker-compose.yml up --build

test:
	cd backend && PYTHONPATH=. pytest -q

lint:
	cd backend && ruff check app tests

format:
	cd backend && ruff format app tests

worker:
	cd backend && PYTHONPATH=. python -m app.workers.worker
