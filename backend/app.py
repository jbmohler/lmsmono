from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from litestar import Litestar
from litestar.di import Provide

from core.config import AppConfig
from core.db import init_pool, close_pool, provide_connection
from api.health import HealthController, PingController
from api.eventlog import EventLogController


config: AppConfig | None = None


@asynccontextmanager
async def lifespan(app: Litestar) -> AsyncGenerator[None, None]:
    global config
    config = AppConfig.load()
    print(f"Config loaded: database={config.database.host}")

    if config.database.host:
        await init_pool(config.database.conninfo)
        print("Database pool initialized")

    yield

    await close_pool()
    print("Database pool closed")


app = Litestar(
    route_handlers=[
        HealthController,
        PingController,
        EventLogController,
    ],
    dependencies={
        "conn": Provide(provide_connection),
    },
    lifespan=[lifespan],
)
