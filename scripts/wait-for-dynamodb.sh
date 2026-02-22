#!/bin/bash
# Wait for DynamoDB (LocalStack) to be ready

set -e

HOST="${DYNAMODB_HOST:-localstack}"
PORT="${DYNAMODB_PORT:-4566}"
TIMEOUT="${WAIT_TIMEOUT:-60}"

echo "⏳ Waiting for DynamoDB at ${HOST}:${PORT}..."

start_time=$(date +%s)

while true; do
    # Try to list tables - this confirms DynamoDB is fully operational
    if curl -s "http://${HOST}:${PORT}/_localstack/health" | grep -q '"dynamodb"'; then
        # Additional check: try to actually list tables
        if aws --endpoint-url="http://${HOST}:${PORT}" dynamodb list-tables --region us-east-1 2>/dev/null; then
            echo "✅ DynamoDB is ready!"
            exit 0
        fi
    fi

    current_time=$(date +%s)
    elapsed=$((current_time - start_time))

    if [ $elapsed -ge $TIMEOUT ]; then
        echo "❌ Timeout waiting for DynamoDB after ${TIMEOUT} seconds"
        exit 1
    fi

    echo "   Waiting... (${elapsed}s elapsed)"
    sleep 2
done
