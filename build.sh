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

if [ -z "${DATABASE_URL:-}" ] && [ -z "${MYSQL_URL:-}" ] && { [ -z "${MYSQL_HOST:-}" ] || [ -z "${MYSQL_USER:-}" ]; }; then
    echo "MySQL configuration is incomplete. Set MYSQL_HOST and MYSQL_USER (or DATABASE_URL) in Render." >&2
    exit 1
fi

echo "Connecting to MySQL and applying migrations..."
# A running web service without a migrated database cannot authenticate users.
# Do not hide a migration failure: failing the deploy exposes the actual database
# configuration error in Render's build log instead of serving HTTP 500 responses.
python manage.py migrate --noinput

echo "=== HarvestHub Build Finished Successfully ==="
