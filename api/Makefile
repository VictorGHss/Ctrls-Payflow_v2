# Makefile para comandos comuns

.PHONY: help install dev test lint format clean docker-build docker-up docker-down

help:
	@echo "PayFlow API - Comandos disponíveis:"
	@echo ""
	@echo "  make install      - Instalar dependências"
	@echo "  make dev          - Rodar API em modo desenvolvimento"
	@echo "  make worker       - Rodar worker em modo desenvolvimento"
	@echo "  make test         - Executar testes"
	@echo "  make test-cov     - Executar testes com coverage"
	@echo "  make lint         - Executar linting (ruff)"
	@echo "  make format       - Formatar código (black)"
	@echo "  make clean        - Limpar cache e arquivos temporários"
	@echo "  make docker-build - Build imagens Docker"
	@echo "  make docker-up    - Iniciar containers"
	@echo "  make docker-down  - Parar containers"
	@echo "  make docker-logs  - Ver logs Docker"
	@echo "  make generate-key - Gerar MASTER_KEY"

install:
	python -m venv .venv
	.\.venv\Scripts\activate && pip install -r requirements.txt

dev:
	uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

worker:
	python -m app.worker

test:
	pytest tests/ -v

test-cov:
	pytest tests/ -v --cov=app --cov-report=html --cov-report=term

lint:
	ruff check app/ tests/

format:
	black app/ tests/

clean:
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name ".pytest_cache" -delete
	find . -type d -name ".mypy_cache" -delete
	find . -type d -name "htmlcov" -delete
	find . -type f -name ".coverage" -delete

docker-build:
	docker-compose build

docker-up:
	docker-compose up -d

docker-down:
	docker-compose down

docker-logs:
	docker-compose logs -f

generate-key:
	@python -c "import base64, secrets; print('MASTER_KEY=' + base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())"

migrate:
	@echo "Migrações com Alembic ainda não implementadas"
	@echo "Use SQLAlchemy ORM para mudanças no schema"

