# CLAUDE.md - Development Guidelines

## Development Progress

**Always read `PLAN.md` at session start** to understand current progress. Update checkboxes as tasks complete. Use the Session Notes section to communicate between sessions.

---

## Project Context

LMS is a mature application with a 20-year-old data model. The PostgreSQL schema is stable and well-established. Development focuses on building a modern web interface while respecting the existing data structures.

## Dependencies (Locked)

### Backend (Python)
- **Python 3.13**
- **FastAPI** (latest)
- **psycopg 3** (async)
- **Pydantic v2**
- **uvicorn** - ASGI server
- **ruff** - linting and formatting
- **mypy** - type checking
- **argon2-cffi** - password hashing
- **pydantic-settings** - environment configuration
- **pytest** + **pytest-asyncio** - testing

### Frontend (Angular)
- **Node.js 22 LTS**
- **pnpm** - package manager
- **Angular 21** - standalone components, signals
- **Tailwind CSS 4**
- **Angular CDK** (matching Angular version)
- **knip** - dead code detection
- **ESLint 9** (flat config) + **Prettier**
- **Vitest** - unit testing
- **Playwright** - e2e testing

### Git Integration
- **No husky, lint-staged, or git hooks from pnpm/Angular**
- Git is controlled manually, not by tooling
- Single repository with `backend/` and `frontend/` directories

### Docker
- **python:3.13-slim-bookworm** base image
- Multi-stage build (Node for frontend build, Python for runtime)

## Architecture Principles

### Backend (Python/FastAPI)

- Use **psycopg3 async** for all database operations
- Connection pooling via `AsyncConnectionPool`
- Write raw SQL queries - no ORM. The schema is stable and SQL is explicit.
- Keep queries in dedicated files under `backend/db/queries/`
- Use Pydantic models for all API request/response validation
- API routes grouped by domain under `backend/api/`

### Frontend (Angular)

- Use **standalone components** (no NgModules)
- Use **signals** for reactive state management
- Tailwind for all styling - no component library CSS
- Angular CDK for accessibility primitives, not Angular Material
- Lazy-load feature modules by route

### Database

- PostgreSQL with managed cloud hosting
- Connect via psycopg3 with SSL
- Schema is READ-ONLY from application perspective - no migrations generated
- Double-entry accounting: every transaction must balance (debits = credits)

## Keyboard Navigation Requirements

This is a keyboard-first application. Every feature must be fully operable via keyboard.

### Implementation Patterns

```typescript
// Use Angular CDK ListKeyManager for list navigation
@ViewChildren(ListItemDirective) items: QueryList<ListItemDirective>;
keyManager = new ListKeyManager(this.items).withWrap().withHomeAndEnd();

// Global shortcuts via HostListener
@HostListener('window:keydown', ['$event'])
handleKeydown(event: KeyboardEvent) {
  if (event.ctrlKey && event.key === 'n') {
    this.newTransaction();
  }
}
```

### Required Shortcuts
- `Ctrl+N` - New transaction
- `Ctrl+S` - Save current form
- `Escape` - Close modal/cancel
- `Arrow keys` - Navigate lists and tables
- `Enter` - Select/open item
- `Tab` - Standard focus navigation

### Focus Management
- Trap focus in modals (`cdkTrapFocus`)
- Return focus to trigger element on modal close
- Auto-focus first input on form open

## Double-Entry Accounting Rules

- Every transaction has 2+ line items
- Sum of debits must equal sum of credits
- Accounts have types: Asset, Liability, Equity, Income, Expense
- Debits increase: Assets, Expenses
- Credits increase: Liabilities, Equity, Income
- Balance Sheet: Assets = Liabilities + Equity
- P&L: Income - Expenses = Net Income

## Multi-Tenant Password Vault

- Tenant isolation is critical - never leak credentials across tenants
- Sharing is explicit and permission-based
- Credentials may link to contacts (e.g., "Bank of America" contact linked to BoA login)
- **Server-side encryption** - credentials encrypted at rest in database

## Code Style

### Python
- Type hints on all functions
- Async functions for I/O operations
- f-strings for formatting
- Snake_case for variables and functions

### TypeScript/Angular
- Strict TypeScript settings
- Interfaces over classes for data shapes
- Reactive patterns with signals
- camelCase for variables, PascalCase for components

### SQL
- UPPERCASE keywords
- snake_case for table/column names
- Explicit column lists (no `SELECT *`)
- Parameterized queries only - never string interpolation

## File Organization

When adding features:
1. Backend route in `backend/api/{feature}.py`
2. SQL queries in `backend/db/queries/{feature}.sql`
3. Pydantic models in `backend/models/{feature}.py`
4. Angular feature module in `frontend/src/app/{feature}/`
5. Update routes in both backend `main.py` and Angular routing

## Testing Approach

- Backend: pytest with pytest-asyncio fixtures
- Frontend: Vitest for unit tests, Playwright for e2e
- Test keyboard navigation explicitly in e2e tests

## Common Commands

```bash
# Backend
cd backend && uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Frontend
cd frontend && pnpm install
cd frontend && pnpm ng serve --open

# Linting
cd frontend && pnpm knip          # dead code detection
cd frontend && pnpm lint          # ESLint
cd backend && ruff check .        # Python linting
cd backend && mypy .              # Type checking

# Testing
cd frontend && pnpm test          # Vitest
cd frontend && pnpm e2e           # Playwright
cd backend && pytest              # pytest

# Build for production
cd frontend && pnpm ng build --configuration production
# Output goes to frontend/dist/ and is served by FastAPI

# Docker build
docker build -t lms .

# Run container
docker run -p 8000:8000 -e DATABASE_URL=postgresql://... lms
```

## API Conventions

- RESTful routes under `/api/`
- JSON request/response bodies
- ISO 8601 dates
- Pagination via `?limit=N&offset=M`
- Error responses: `{ "detail": "message" }`

## Authentication

- **Session cookies** validated server-side on every request
- Sessions stored in PostgreSQL
- Secure cookie attributes: `HttpOnly`, `Secure`, `SameSite=Strict`
- Session expiration and renewal handling
- Angular HTTP interceptor to handle 401 responses

## Security Notes

- Password vault requires careful handling
- Use parameterized queries exclusively
- Validate tenant access on every password endpoint
- HTTPS in production
- Secure cookie settings for sessions
- Argon2 for password hashing
