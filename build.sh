#!/usr/bin/env bash
set -o errexit

echo "=== Starting HarvestHub Production Build ==="

# If executed from root, navigate to backend
if [ -d "backend" ]; then
    cd backend
fi

pip install --upgrade pip
pip install -r requirements.txt
python manage.py collectstatic --noinput

if [ -n "$MYSQL_HOST" ] || [ -n "$DATABASE_URL" ]; then
    echo "Connecting to MySQL and applying migrations..."
    python manage.py migrate
else
    echo "Skipping migrate step (MYSQL_HOST / DATABASE_URL not yet configured in environment variables)."
fi

echo "=== HarvestHub Build Finished Successfully ==="
