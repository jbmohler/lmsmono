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
- **Python 3.13** with **Litestar** - async web framework with guards and dependency injection
- **psycopg3** - async PostgreSQL driver with connection pooling
- **uvicorn** - ASGI server

### Frontend
- **Angular 21** - standalone components, signals-based reactivity
- **Tailwind CSS 4** - utility-first CSS, mobile-first responsive design
- **Angular CDK** - accessibility and keyboard navigation primitives
- **pnpm** - package manager

### Database
- **PostgreSQL** (managed cloud instance)

### Deployment
- Single Docker container serving both API and static frontend
- Litestar serves Angular build artifacts from `/`
- API routes under `/api/`

## Project Structure

```
/
├── backend/
│   ├── app.py               # Litestar application entry
│   ├── core/                # Config, DB pool, auth, middleware
│   ├── api/                 # Route controllers by domain
│   └── requirements.txt
├── frontend/                # Angular application
│   ├── src/
│   │   ├── app/             # Feature modules (lazy-loaded by route)
│   │   └── styles.css       # Tailwind entry
│   └── package.json
├── secrets/
│   ├── config.example.json  # Config template (committed)
│   └── config.json          # Actual config (gitignored)
├── Dockerfile               # Production multi-stage build
├── docker-compose.yml       # Local development environment
├── CLAUDE.md
└── README.md
```

## Development

All tooling runs inside Docker containers.

### First-time setup

```bash
cp secrets/config.example.json secrets/config.json
# Edit secrets/config.json with your local settings
```

### Start the dev environment

```bash
docker compose up -d
docker compose logs -f       # Follow logs
```

Access the app at **http://localhost:8080** (Nginx proxies to frontend dev server and backend).

PostgreSQL is also exposed directly on port **5432**.

### Common dev commands

```bash
# Linting
docker compose exec backend ruff check .
docker compose exec backend mypy .
docker compose exec frontend pnpm lint
docker compose exec frontend pnpm knip      # Dead code detection

# Testing
docker compose exec backend pytest
docker compose exec frontend pnpm test      # Vitest unit tests
docker compose exec frontend pnpm e2e       # Playwright e2e tests

# Shell access
docker compose exec backend bash
docker compose exec frontend sh
docker compose exec postgres psql -U lms -d lms
```

## Production Build

The production image is a multi-stage build: Node.js compiles the Angular app, then Python serves both the API and the compiled static files from a single container.

### Build the image

```bash
docker build -t lms .
```

### Run the image

The backend reads its config from a Docker secret at `/run/secrets/config.json`. Point it at your managed database by setting the appropriate host and credentials there.

```bash
docker run -p 8000:8000 \
  -v /path/to/config.json:/run/secrets/config.json:ro \
  lms
```

The app is then available at **http://localhost:8000**.

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
- Secure credential storage with server-side encryption
- Integration with contacts for credential association

## Reports

- **Profit & Loss** - Income and expense summary by period
- **Balance Sheet** - Assets, liabilities, and equity snapshot
- **Transaction Register** - Detailed transaction listing with filters
