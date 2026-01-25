# Backend Development Guide

## Framework: Litestar

This backend uses [Litestar](https://litestar.dev/) - a modern async Python web framework with native async support, dependency injection, and guards for authorization.

## Project Structure

```
backend/
├── app.py              # Litestar app entry point
├── core/
│   ├── config.py       # AppConfig via dataclasses
│   ├── db.py           # Connection pool + query executors
│   ├── responses.py    # Column metadata + response models
│   └── guards.py       # Capability-based auth guards
├── api/
│   ├── health.py       # Health/ping controllers
│   ├── eventlog.py     # Event log controller
│   └── ...             # Add new controllers here
└── queries/            # SQL files (optional, for complex queries)
```

## Adding a New Endpoint

### 1. Create a Controller

```python
# api/contacts.py
from dataclasses import dataclass

import psycopg
from litestar import Controller, get, post, put, delete
from litestar.params import Parameter

import core.db as db
from core.responses import ColumnMeta, MultiRowResponse, SingleRowResponse
from core.guards import require_capability


# Define columns once, reuse across endpoints
CONTACT_COLUMNS = [
    ColumnMeta(key="id", label="ID", type="uuid"),
    ColumnMeta(key="name", label="Name", type="string"),
    ColumnMeta(key="email", label="Email", type="string"),
]


@dataclass
class ContactCreate:
    name: str
    email: str | None = None


class ContactsController(Controller):
    path = "/api/contacts"
    tags = ["contacts"]

    @get(guards=[require_capability("contacts:read")])
    async def list_contacts(
        self,
        conn: psycopg.AsyncConnection,
        limit: int = Parameter(default=50, le=500),
        offset: int = Parameter(default=0, ge=0),
    ) -> MultiRowResponse:
        return await db.select_many(
            conn,
            """
            SELECT id, name, email
            FROM contacts
            ORDER BY name
            LIMIT %(limit)s OFFSET %(offset)s
            """,
            {"limit": limit, "offset": offset},
            columns=CONTACT_COLUMNS,
        )

    @get("/{contact_id:uuid}", guards=[require_capability("contacts:read")])
    async def get_contact(
        self,
        conn: psycopg.AsyncConnection,
        contact_id: str,
    ) -> SingleRowResponse:
        return await db.select_one(
            conn,
            "SELECT id, name, email FROM contacts WHERE id = %(id)s",
            {"id": contact_id},
            columns=CONTACT_COLUMNS,
        )

    @post(guards=[require_capability("contacts:write")], status_code=201)
    async def create_contact(
        self,
        conn: psycopg.AsyncConnection,
        data: ContactCreate,
    ) -> SingleRowResponse:
        row = await db.execute_returning(
            conn,
            """
            INSERT INTO contacts (name, email)
            VALUES (%(name)s, %(email)s)
            RETURNING id, name, email
            """,
            {"name": data.name, "email": data.email},
        )
        return SingleRowResponse(columns=CONTACT_COLUMNS, data=row)
```

### 2. Register in app.py

```python
from api.contacts import ContactsController

app = Litestar(
    route_handlers=[
        HealthController,
        PingController,
        EventLogController,
        ContactsController,  # Add here
    ],
    ...
)
```

## Response Format

All list/detail endpoints return self-describing responses:

```python
# Single row
SingleRowResponse(
    columns=[ColumnMeta(key="id", label="ID", type="uuid"), ...],
    data={"id": "...", "name": "..."}
)

# Multiple rows
MultiRowResponse(
    columns=[ColumnMeta(key="id", label="ID", type="uuid"), ...],
    data=[{"id": "...", "name": "..."}, ...]
)
```

### Column Types

| Type | Description |
|------|-------------|
| `string` | Text |
| `number` | Integer or float |
| `currency` | Monetary value |
| `date` | Date only (ISO 8601) |
| `datetime` | Date and time (ISO 8601) |
| `boolean` | True/false |
| `uuid` | UUID primary key |
| `ref` | Foreign key reference: `{"id": "...", "name": "..."}` |

## Database Queries

Use the query executors in `core/db.py`:

```python
# Single row (raises NotFoundException if not found)
result = await db.select_one(conn, "SELECT ...", {"param": value}, columns=COLS)

# Multiple rows
result = await db.select_many(conn, "SELECT ...", {"param": value}, columns=COLS)

# Insert/update with RETURNING
row = await db.execute_returning(conn, "INSERT ... RETURNING ...", {"param": value})

# Execute without return value
count = await db.execute(conn, "DELETE FROM ... WHERE ...", {"param": value})
```

### Parameter Style

Use `%(name)s` style parameters (psycopg3 dict params):

```python
await db.select_one(
    conn,
    "SELECT * FROM users WHERE id = %(user_id)s AND tenant = %(tenant)s",
    {"user_id": user_id, "tenant": tenant_id},
    columns=USER_COLUMNS,
)
```

## Authorization Guards

Protect endpoints with capability guards:

```python
from core.guards import require_capability

@get(guards=[require_capability("resource:read")])
async def list_items(self, conn: psycopg.AsyncConnection) -> MultiRowResponse:
    ...

@post(guards=[require_capability("resource:write")])
async def create_item(self, conn: psycopg.AsyncConnection, data: ItemCreate) -> SingleRowResponse:
    ...
```

Capabilities follow the pattern `resource:action`:
- `contacts:read`, `contacts:write`
- `transactions:read`, `transactions:write`
- `admin:users`, `admin:settings`

## Dependency Injection

The database connection is automatically injected via Litestar DI:

```python
# Defined in app.py
dependencies={"conn": Provide(provide_connection)}

# Available in any controller method
async def my_endpoint(self, conn: psycopg.AsyncConnection) -> ...:
```

Add custom dependencies the same way:

```python
async def provide_current_user(request: Request) -> User:
    ...

# In app.py
dependencies={
    "conn": Provide(provide_connection),
    "current_user": Provide(provide_current_user),
}
```

## Request Validation

Use dataclasses for request bodies:

```python
@dataclass
class TransactionCreate:
    date: datetime.date
    description: str
    lines: list[TransactionLine]

@dataclass
class TransactionLine:
    account_id: str
    amount: float
    is_debit: bool
```

Use `Parameter()` for query/path params with validation:

```python
from litestar.params import Parameter

@get()
async def list_items(
    self,
    limit: int = Parameter(default=50, le=500, ge=1),
    offset: int = Parameter(default=0, ge=0),
    search: str | None = Parameter(default=None, max_length=100),
) -> MultiRowResponse:
```

## Error Handling

Use Litestar's built-in exceptions:

```python
from litestar.exceptions import (
    NotFoundException,           # 404
    NotAuthorizedException,      # 401
    PermissionDeniedException,   # 403
    HTTPException,               # Generic (specify status_code)
)

# In endpoint
if not row:
    raise NotFoundException(detail="Contact not found")

# With custom status
raise HTTPException(status_code=409, detail="Conflict: duplicate entry")
```

## Running the Backend

```bash
# Development (in Docker)
docker-compose up backend

# Or directly
uvicorn app:app --reload --host 0.0.0.0 --port 8000

# Linting
ruff check .
mypy .

# Testing
pytest
```

## Key Differences from FastAPI

| FastAPI | Litestar |
|---------|----------|
| `@app.get("/path")` | `@get()` on Controller method |
| `Depends(func)` | `dependencies={"name": Provide(func)}` |
| `HTTPException(status_code=404)` | `NotFoundException()` |
| `response_model=Model` | Return type annotation |
| Routers | Controllers |
| `Query()`, `Path()` | `Parameter()` |
