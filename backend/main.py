import contextlib
import json
import os
import pathlib

import fastapi
import pydantic


class HealthResponse(pydantic.BaseModel):
    status: str
    config_loaded: bool
    database_host: str | None = None


config: dict = {}


@contextlib.asynccontextmanager
async def lifespan(app: fastapi.FastAPI):
    global config
    config_path = os.environ.get("CONFIG_FILE", "/run/secrets/config.json")

    if pathlib.Path(config_path).exists():
        with open(config_path) as f:
            config = json.load(f)
        print(f"Config loaded from {config_path}")
    else:
        print(f"Warning: Config file not found at {config_path}")

    yield


app = fastapi.FastAPI(title="LMS API", lifespan=lifespan)


@app.get("/api/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(
        status="ok",
        config_loaded=bool(config),
        database_host=config.get("database", {}).get("host"),
    )


@app.get("/api/ping")
async def ping() -> dict:
    return {"message": "pong"}
