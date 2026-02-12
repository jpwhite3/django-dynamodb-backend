# GEMINI.md

## Project Overview

The overall goal of this project is to create a DynamoDB adapter that will allow Django to work with DynamoDB just like it would with supported relational databases. In addition, it aims to have 100% compatibility with the Django admin interface. This would be released as an open source project for people to be able to run Django and DynamoDB in an AWS serverless environment. Currently the project is only partially complete.

The core of the project is the `dynamodb_adapter` app, which acts as a database backend for Django. It translates Django's query language into efficient DynamoDB operations, automatically leveraging features like Global Secondary Indexes (GSIs) for optimized filtering and sorting.

The application also includes an interactive demo environment, allowing developers to quickly explore its features with sample data.

**Key Technologies:**

*   **Backend:** Python, Django
*   **Database:** Amazon DynamoDB
*   **Packaging:** Pip, Setuptools
*   **Containerization:** Docker, Docker Compose

## Building and Running

### Interactive Demo (Recommended)

The quickest way to get started is to run the interactive demo, which includes a pre-configured Django project, DynamoDB local instance, and sample data.

```bash
# Start the interactive demo environment
make demo
```

Once running, the following services will be available:

*   **Django Admin:** `http://localhost:8001/admin/` (Credentials: `admin`/`admin123`)
*   **DynamoDB UI:** `http://localhost:8002/`

### Manual Installation

For development or integration into an existing project, you can install the package and its dependencies using `pip`.

```bash
# Install dependencies
pip install -r requirements.txt

# Create initial database migrations
python manage.py dynamodb_makemigrations

# Apply migrations to create DynamoDB tables
python manage.py dynamodb_migrate

# Start the development server
python manage.py runserver
```

### Running Tests

The project includes a comprehensive test suite. To run the tests, use the following command:

```bash
# Run the test suite
python tests/test_runner_complete.py
```

## Development Conventions

*   **Code Style:** The project uses `black` for code formatting and `isort` for import sorting. You can format the code using the `make format` command.
*   **Linting:** `flake8` is used for linting. You can run the linter using the `make lint` command.
*   **Migrations:** Database migrations are managed through the `dynamodb_makemigrations` and `dynamodb_migrate` management commands.
*   **Contributing:** Contributions are welcome. Please refer to the `CONTRIBUTING.md` file for more details.
