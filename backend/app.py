import traceback
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from pathlib import Path

from litestar import Litestar, Request, Response
from litestar.di import Provide
from litestar.exceptions import HTTPException, NotFoundException
from litestar.static_files import StaticFilesConfig

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

_index_html = Path("static/index.html")


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
    """Serve index.html for non-API 404s to support SPA client-side routing."""
    if not request.url.path.startswith("/api/") and _index_html.exists():
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
    static_files_config=(
        [StaticFilesConfig(directories=[Path("static")], path="/", html_mode=True)]
        if Path("static").exists()
        else []
    ),
)
