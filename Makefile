# Django DynamoDB Backend - Development Makefile

.PHONY: help local-dev stop clean logs shell test build install lint format

# Default target
help:
	@echo "🚀 Django DynamoDB Backend - Development Commands"
	@echo "================================================"
	@echo ""
	@echo "Development Environment:"
	@echo "  local-dev   - Start local development environment with LocalStack"
	@echo "  stop        - Stop local development environment"
	@echo "  clean       - Clean up Docker environment"
	@echo "  logs        - View application logs"
	@echo "  shell       - Access Django shell in the development environment"
	@echo ""
	@echo "Testing & Code Quality:"
	@echo "  test        - Run test suite"
	@echo "  lint        - Run code quality checks (flake8)"
	@echo "  format      - Format code (black)"
	@echo ""
	@echo "Utilities:"
	@echo "  install     - Install development dependencies"
	@echo "  build       - Build Docker images"

# Development Environment Commands
local-dev:
	@echo "🚀 Starting local development environment..."
	docker compose -f docker-compose.yml up --build

stop:
	@echo "🔌 Stopping local development environment..."
	docker-compose -f docker-compose.yml down

clean:
	@echo "🧹 Cleaning Docker Environment..."
	docker compose -f docker-compose.yml down -v
	docker system prune -f

logs:
	docker compose -f docker-compose.yml logs -f web

shell:
	@echo "🐚 Opening Django Shell..."
	docker compose -f docker-compose.yml exec web python manage.py shell

# Testing & Code Quality Commands
test:
	@echo "🧪 Running Test Suite..."
	docker compose -f docker-compose.yml build test
	docker compose -f docker-compose.yml run --rm test pipenv run python -m pytest -v

test-local:
	@echo "🧪 Running Test Suite on host machine..."
	docker compose up -d localstack redis
	PYTHONPATH=src pipenv run python run_tests.py $(TEST_PATH)
	docker compose down

lint:
	@echo "🔍 Running Code Quality Checks..."
	flake8 .

format:
	@echo "✨ Formatting Code..."
	black .

# Setup Commands
install:
	@echo "📦 Installing Development Dependencies..."
	pip install -r requirements/dev.txt

build:
	@echo "🔨 Building Docker Images..."
	docker compose -f docker-compose.yml build