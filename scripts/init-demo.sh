#!/bin/bash
# Initialize the demo environment
# This script runs inside the container after services are up

set -e

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║      Django DynamoDB Backend - Demo Initialization           ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Wait for DynamoDB to be ready
echo "🔄 Step 1/6: Waiting for DynamoDB..."
/app/scripts/wait-for-dynamodb.sh

# Create DynamoDB sessions table
echo ""
echo "🔄 Step 2/6: Creating DynamoDB sessions table..."
python manage.py dynamodb_create_session_table 2>&1 || echo "   (Sessions table may already exist)"

# Create DynamoDB users table and admin user
echo ""
echo "🔄 Step 3/6: Creating DynamoDB users table and admin user..."
python manage.py dynamodb_create_user_table --create-admin 2>&1 || echo "   (Users table may already exist)"

# Run Django migrations (for contenttypes only, no auth/sessions DB tables needed)
echo ""
echo "🔄 Step 4/6: Running Django contenttypes migration..."
python manage.py migrate contenttypes --noinput 2>/dev/null || echo "   (Contenttypes migration skipped)"

# Create DynamoDB tables for demo apps
echo ""
echo "🔄 Step 5/6: Creating DynamoDB tables for demo apps..."
python manage.py dynamodb_migrate 2>/dev/null || echo "   (DynamoDB tables may already exist)"

# Seed demo data
echo ""
echo "🔄 Step 6/6: Seeding demo data..."
python manage.py setup_demo_data --size small 2>&1 || {
    echo "   ⚠️  Demo data seeding encountered issues (tables may need to be created first)"
    echo "   You can manually run: python manage.py setup_demo_data --size small"
}

# Print success banner
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                    🎉 Demo Ready!                            ║"
echo "╠══════════════════════════════════════════════════════════════╣"
echo "║                                                              ║"
echo "║  Django Admin:  http://localhost:8001/admin/                 ║"
echo "║                                                              ║"
echo "║  Login Credentials:                                          ║"
echo "║    Username: admin                                           ║"
echo "║    Password: admin123                                        ║"
echo "║                                                              ║"
echo "║  Features to Explore:                                        ║"
echo "║    • Blog posts with categories and tags                     ║"
echo "║    • E-commerce products and orders                          ║"
echo "║    • Advanced filtering and search                           ║"
echo "║    • Batch operations and admin actions                      ║"
echo "║                                                              ║"
echo "║  🚀 Running 100% on DynamoDB (no relational DB!)             ║"
echo "║                                                              ║"
echo "║  Press Ctrl+C to stop the server                             ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Start the Django development server
exec python manage.py runserver 0.0.0.0:8000
