# Django DynamoDB Admin - Development Makefile

# Virtual environment Python
PYTHON = .venv/bin/python
PIP = .venv/bin/pip

.PHONY: help demo demo-quick demo-large clean logs shell test status build

# Default target
help:
	@echo "🚀 Django DynamoDB Admin - Development Commands"
	@echo "================================================"
	@echo ""
	@echo "Demo Environment:"
	@echo "  demo        - Start interactive demo with sample data"
	@echo "  demo-quick  - Start demo with minimal data (fast)"
	@echo "  demo-large  - Start demo with large dataset"
	@echo "  status      - Check demo environment status"
	@echo "  clean       - Clean up demo environment"
	@echo ""
	@echo "Development:"
	@echo "  logs        - View demo application logs"
	@echo "  shell       - Access Django shell in demo environment"
	@echo "  test        - Run test suite"
	@echo "  build       - Build Docker images"
	@echo ""
	@echo "Utilities:"
	@echo "  install     - Install development dependencies"
	@echo "  lint        - Run code quality checks"
	@echo "  docs        - Generate documentation"

# Demo Environment Commands
demo:
	@echo "🚀 Starting Django DynamoDB Admin Interactive Demo..."
	@echo "This will start DynamoDB Local and generate sample data."
	@echo "Access: http://localhost:8001/admin/ (admin/admin123)"
	@echo ""
	docker-compose -f docker-compose.dev.yml up --build

demo-quick:
	@echo "⚡ Starting Quick Demo (minimal data)..."
	@docker-compose -f docker-compose.dev.yml up -d dynamodb-local redis
	@sleep 5
	@docker-compose -f docker-compose.dev.yml run --rm django-app python manage.py setup_demo_data --quick --settings=interactive_demo.settings
	@docker-compose -f docker-compose.dev.yml up django-app dynamodb-admin-ui

demo-large:
	@echo "📊 Starting Large Dataset Demo..."
	@docker-compose -f docker-compose.dev.yml up -d dynamodb-local redis
	@sleep 5  
	@docker-compose -f docker-compose.dev.yml run --rm django-app python manage.py setup_demo_data --size large --settings=interactive_demo.settings
	@docker-compose -f docker-compose.dev.yml up django-app dynamodb-admin-ui

status:
	@echo "🔍 Checking Demo Environment Status..."
	docker-compose -f docker-compose.dev.yml exec django-app python manage.py demo_status --detailed --settings=interactive_demo.settings || \
	docker-compose -f docker-compose.dev.yml run --rm django-app python manage.py demo_status --detailed --settings=interactive_demo.settings

clean:
	@echo "🧹 Cleaning Demo Environment..."
	docker-compose -f docker-compose.dev.yml down -v
	docker system prune -f

# Development Commands
logs:
	docker-compose -f docker-compose.dev.yml logs -f django-app

shell:
	@echo "🐚 Opening Django Shell..."
	docker-compose -f docker-compose.dev.yml exec django-app python manage.py shell --settings=interactive_demo.settings

test:
	@echo "🧪 Running Test Suite..."
	cd django_dynamo_admin && PYTHONPATH=$(PWD)/django_dynamo_admin $(PWD)/.venv/bin/python tests/test_runner_complete.py --quick

test-full:
	@echo "🧪 Running Full Test Suite..."
	cd django_dynamo_admin && PYTHONPATH=$(PWD)/django_dynamo_admin $(PWD)/.venv/bin/python tests/test_runner_complete.py

build:
	@echo "🔨 Building Docker Images..."
	docker-compose -f docker-compose.dev.yml build

# Setup Commands
install:
	@echo "📦 Installing Development Dependencies..."
	$(PIP) install -r requirements-dev.txt
	$(PIP) install -r requirements-demo.txt

install-demo:
	@echo "📦 Installing Demo Dependencies..."
	pip install -r requirements-demo.txt

# Code Quality
lint:
	@echo "🔍 Running Code Quality Checks..."
	.venv/bin/black --check .
	.venv/bin/isort --check-only .
	.venv/bin/flake8 .

format:
	@echo "✨ Formatting Code..."
	.venv/bin/black .
	.venv/bin/isort .

# Legacy commands (maintained for compatibility)
bootstrap:
	- pipenv --rm
	pipenv update

reqs:
	pipenv requirements > requirements.txt

clean-pyc: ## remove Python file artifacts
	find . -name '*.pyc' -exec rm -f {} +
	find . -name '*.pyo' -exec rm -f {} +
	find . -name '*~' -exec rm -f {} +
	find . -name '__pycache__' -exec rm -fr {} +

migrate:
	$(PYTHON) django_dynamo_admin/manage.py makemigrations dynamodb_adapter
	$(PYTHON) django_dynamo_admin/manage.py migrate dynamodb_adapter

run: migrate
	$(PYTHON) django_dynamo_admin/manage.py runserver

django-shell:
	$(PYTHON) django_dynamo_admin/manage.py shell

stop-dynamo:
	- docker container stop -t 60 dynamodb-local
	- docker container rm dynamodb-local

start-dynamo: stop-dynamo
	docker run -p 9000:8000 --name dynamodb-local --detach -it amazon/dynamodb-local

create-su:
	python3 django_dynamo_admin/manage.py createsuperuser