# HarvestHub

HarvestHub is a multi-farmer farm-management platform built with Django REST Framework, React, and MySQL. Every API queryset is scoped to the authenticated farmer, so records cannot be read or modified across accounts.

## Modules

- Secure farmer registration, login, logout, and profile
- Dashboard analytics from live farm records
- Fields, crop plans and rotation history
- Farm operations and schedule calendar/list
- Expenses, harvest records, and basic historical forecasts
- Equipment, maintenance, and utilisation records
- Inventory with stock-in/stock-out transaction ledger and non-negative quantity protection
- Filtered reports and CSV export

## Prerequisites

- Python 3.11+
- Node.js 20+
- MySQL 8+ with a database and account created for HarvestHub

## Start the backend

```powershell
cd backend
Copy-Item .env.example .env
# Set the MySQL values in .env
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

The backend intentionally uses MySQL only. It will refuse to start until MySQL credentials are supplied.

## Start the frontend

```powershell
cd frontend
npm install
npm run dev
```

The Vite server proxies `/api` to `http://127.0.0.1:8000`.

## Optional demo data

After creating a MySQL database and applying migrations, run the following. It creates/updates only the named demo account; it never injects records into other farmers' accounts.

```powershell
cd backend
python manage.py seed_demo --username demo_farmer --email demo@example.com --password "ChangeMe123!"
```

## Tests

```powershell
cd backend
python manage.py test farm
```

Tests use Django's test database and therefore require the MySQL connection in `.env`.
