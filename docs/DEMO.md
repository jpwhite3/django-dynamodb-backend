# Running the Demo

The repository ships with a runnable demo project under `examples/demo_project/` that exercises the full stack — DynamoDB-backed models, admin, authentication, and sessions — against a local DynamoDB instance.

## Option 1: Docker (recommended)

The fastest path: one command brings up a local DynamoDB emulator, runs migrations, seeds sample data, and starts a Django server.

```bash
git clone https://github.com/jpwhite3/django-dynamodb-backend.git
cd django-dynamodb-backend
make demo
```

This starts:

- A local DynamoDB emulator (LocalStack)
- The Django development server at <http://localhost:8001/admin/>
- Sample data (blog posts, products, orders)

Login: `admin` / `admin123`.

No Redis, PostgreSQL, or SQLite is involved — everything runs on DynamoDB.

### Demo commands

| Command          | What it does                                |
| ---------------- | ------------------------------------------- |
| `make demo`      | Start the demo                              |
| `make demo-stop` | Stop the demo                               |
| `make demo-reset`| Reset (clear data) and restart              |
| `make demo-logs` | View demo logs                              |
| `make demo-shell`| Open a Django shell in the demo environment |

## Option 2: Local Python, no Docker

If you would rather run Python directly and bring up a local DynamoDB yourself (or point at a real AWS account), install the package and a local DynamoDB endpoint of your choice.

```bash
git clone https://github.com/jpwhite3/django-dynamodb-backend.git
cd django-dynamodb-backend
pip install -e ".[dev]"

# Pick one local DynamoDB option, for example LocalStack:
#   https://docs.localstack.cloud/getting-started/installation/
localstack start -d

# Run the test suite to confirm the install works
python -m pytest tests/
```

You can then point `DATABASES['default']['OPTIONS']['endpoint_url']` at your local DynamoDB (default `http://localhost:4566` for LocalStack, `http://localhost:8000` for Amazon DynamoDB Local) and run the demo project's management commands and dev server manually.

## See also

- [Migration Tutorial](MIGRATION_TUTORIAL.md) — adopt the package in an existing Django project
- [Deployment Guide](DEPLOYMENT_GUIDE.md) — production and AWS Lambda deployment
- [Contributing](../CONTRIBUTING.md) — full development environment setup
