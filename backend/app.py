import mimetypes
import traceback
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from litestar import Litestar, Request, Response
from litestar.di import Provide
from litestar.exceptions import HTTPException, NotFoundException

from core.config import AppConfig
from core.crypto import init_crypto
from core.auth import provide_current_user
from core.db import init_pool, close_pool, provide_connection
from api.auth import AuthController
from api.health import HealthController, PingController
from api.eventlog import EventLogController
from api.accounts import AccountTypesController, AccountsController
from api.journals import JournalsController
from api.transactions import TransactionsController
from api.contacts import ContactsController
from api.roles import CapabilitiesController, RolesController
from api.users import UsersController
from api.financials import FinancialsController
from api.passwords.passwords import PasswordGeneratorController
from api.reconcile import ReconcileController
from core.middleware import SessionMiddleware


config: AppConfig | None = None

_static_dir = Path("static")
_index_html = _static_dir / "index.html"


def internal_error_handler(request: Request, exc: Exception) -> Response:
    if isinstance(exc, HTTPException):
        return Response(
            content={"detail": exc.detail},
            media_type="application/json",
            status_code=exc.status_code,
        )
    print(f"ERROR {request.method} {request.url.path}")
    print(traceback.format_exc())
    return Response(
        content={"detail": "Internal server error"},
        media_type="application/json",
        status_code=500,
    )


def spa_fallback(request: Request, exc: NotFoundException) -> Response:
    """Serve static files or index.html for non-API 404s (SPA routing)."""
    path = request.url.path
    if path.startswith("/api/"):
        return Response(
            content={"detail": exc.detail},
            media_type="application/json",
            status_code=404,
        )
    # Try to serve the file from ./static
    candidate = _static_dir / path.lstrip("/")
    if candidate.is_file():
        mime, _ = mimetypes.guess_type(candidate.name)
        return Response(
            content=candidate.read_bytes(),
            media_type=mime or "application/octet-stream",
            status_code=200,
        )
    # SPA fallback: any unmatched non-API route gets index.html
    if _index_html.exists():
        return Response(
            content=_index_html.read_bytes(),
            media_type="text/html",
            status_code=200,
        )
    return Response(
        content={"detail": exc.detail},
        media_type="application/json",
        status_code=404,
    )


@asynccontextmanager
async def lifespan(app: Litestar) -> AsyncGenerator[None, None]:
    global config
    config = AppConfig.load()
    print(f"Config loaded: database={config.database.host}")

    if config.database.host:
        await init_pool(config.database.conninfo)
        print("Database pool initialized")

    if config.encryption.vault_key:
        init_crypto(config.encryption.vault_key)
        print("Vault encryption initialized")

    yield

    await close_pool()
    print("Database pool closed")


app = Litestar(
    route_handlers=[
        AuthController,
        HealthController,
        PingController,
        EventLogController,
        AccountTypesController,
        AccountsController,
        JournalsController,
        TransactionsController,
        ContactsController,
        CapabilitiesController,
        RolesController,
        UsersController,
        FinancialsController,
        PasswordGeneratorController,
        ReconcileController,
    ],
    dependencies={
        "conn": Provide(provide_connection),
        "current_user": Provide(provide_current_user),
    },
    middleware=[SessionMiddleware],
    lifespan=[lifespan],
    exception_handlers={404: spa_fallback, Exception: internal_error_handler},
)
