.PHONY: up down logs rebuild test

up:        ## Build and start the full stack (frontend :3000, backend :8000)
	docker compose up --build -d

down:      ## Stop the stack (data volume is kept)
	docker compose down

logs:      ## Follow logs
	docker compose logs -f

rebuild:   ## Rebuild images from scratch
	docker compose build --no-cache

test:      ## Run backend tests (needs backend/.venv, see README)
	cd backend && python -m pytest -q
