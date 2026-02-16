# Quickstart

This guide provides a quick overview of the development workflow for this project.

## Local Development

To start a local development environment, run the following command:

```bash
make local-dev
```

This will start a LocalStack container and the Django development server. The application will be available at `http://localhost:8000`.

To stop the local development environment, run:

```bash
make stop
```

## Testing

To run the test suite, use the following command:

```bash
make test
```

## Code Quality

To check for linting errors, run:

```bash
make lint
```

To automatically format the code, run:

```bash
make format
```
