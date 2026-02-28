from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from litestar import Litestar
from litestar.di import Provide

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
)
