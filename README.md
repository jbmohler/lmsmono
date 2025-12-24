# LMS - Ledger Management System

A personal and family financial management application combining double-entry accounting, contact management, and a multi-tenant password vault.

## Overview

LMS provides integrated management of:

- **Double-Entry Transactions** - Full double-entry bookkeeping with standard accounting reports (Profit & Loss, Balance Sheet)
- **Contact Management** - Payees, vendors, and related entities linked to transactions
- **Password Vault** - Multi-tenant password manager with family sharing capabilities

The underlying data model has been in production use for approximately 20 years.

## Tech Stack

### Backend
- **Python** with **FastAPI** - async API framework with auto-generated OpenAPI documentation
- **psycopg3** - async PostgreSQL driver with connection pooling
- **Pydantic** - request/response validation

### Frontend
- **Angular 17+** - standalone components, signals-based reactivity
- **Tailwind CSS** - utility-first CSS, mobile-first responsive design
- **Angular CDK** - accessibility and keyboard navigation primitives

### Database
- **PostgreSQL** (managed cloud instance)

### Deployment
- Single Docker container serving both API and static frontend
- FastAPI serves Angular build artifacts from `/`
- API routes under `/api/`

## Project Structure

```
/
├── backend/
│   ├── main.py              # FastAPI application entry
│   ├── api/                 # Route modules
│   │   ├── transactions.py
│   │   ├── accounts.py
│   │   ├── contacts.py
│   │   ├── passwords.py
│   │   └── reports.py
│   ├── db/                  # Database layer
│   │   ├── pool.py          # psycopg connection pool
│   │   └── queries/         # SQL queries
│   ├── models/              # Pydantic models
│   └── requirements.txt
├── frontend/                # Angular application
│   ├── src/
│   │   ├── app/
│   │   │   ├── transactions/
│   │   │   ├── accounts/
│   │   │   ├── contacts/
│   │   │   ├── passwords/
│   │   │   └── reports/
│   │   └── styles.css       # Tailwind entry
│   ├── angular.json
│   └── package.json
├── Dockerfile
├── docker-compose.yml       # Local development with PostgreSQL
├── CLAUDE.md
└── README.md
```

## Key Features

### Keyboard Navigation
- Full keyboard accessibility for desktop power users
- Arrow key navigation in lists and tables (Angular CDK ListKeyManager)
- Global keyboard shortcuts for common actions
- Focus management for modals and dialogs

### Mobile Support
- Responsive design via Tailwind breakpoints
- Touch-friendly UI components
- Simplified navigation for smaller screens

### Multi-Tenant Password Sharing
- Family/group password sharing with granular permissions
- Secure credential storage
- Integration with contacts for credential association

## Development

```bash
# Local development with docker-compose
docker-compose up -d

# Backend only
cd backend && pip install -r requirements.txt && uvicorn main:app --reload

# Frontend only
cd frontend && npm install && ng serve
```

## Reports

- **Profit & Loss** - Income and expense summary by period
- **Balance Sheet** - Assets, liabilities, and equity snapshot
- **Transaction Register** - Detailed transaction listing with filters
