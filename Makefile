# Django DynamoDB Backend - Development Makefile

.PHONY: help demo demo-stop demo-reset demo-logs demo-shell local-dev stop clean logs shell test build install lint format

# Default target
help:
	@echo "🚀 Django DynamoDB Backend - Development Commands"
	@echo "================================================"
	@echo ""
	@echo "Quick Start (Recommended for newcomers):"
	@echo "  demo        - 🎯 One command to start everything with sample data"
	@echo ""
	@echo "Demo Commands:"
	@echo "  demo        - Start demo with DynamoDB, sample data, and Django server"
	@echo "  demo-stop   - Stop the demo environment"
	@echo "  demo-reset  - Reset demo (clear data and reinitialize)"
	@echo "  demo-logs   - View demo logs"
	@echo "  demo-shell  - Open Django shell in demo environment"
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

# ============================================
# Demo Commands (Quick Start for Newcomers)
# ============================================

demo:
	@echo ""
	@echo "╔══════════════════════════════════════════════════════════════╗"
	@echo "║        Django DynamoDB Backend - Demo Environment            ║"
	@echo "╚══════════════════════════════════════════════════════════════╝"
	@echo ""
	@echo "Starting demo environment with:"
	@echo "  • LocalStack (DynamoDB)"
	@echo "  • Redis (caching)"
	@echo "  • Django development server"
	@echo "  • Sample data (blog posts, products, orders)"
	@echo ""
	docker compose --profile demo up --build

demo-stop:
	@echo "🛑 Stopping demo environment..."
	docker compose --profile demo down

demo-reset:
	@echo "🔄 Resetting demo environment..."
	docker compose --profile demo down -v
	@echo "✅ Demo data cleared. Run 'make demo' to start fresh."

demo-logs:
	@echo "📋 Viewing demo logs..."
	docker compose --profile demo logs -f demo

demo-shell:
	@echo "🐚 Opening Django shell in demo environment..."
	docker compose --profile demo exec demo python manage.py shell

# ============================================
# Development Environment Commands
# ============================================

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