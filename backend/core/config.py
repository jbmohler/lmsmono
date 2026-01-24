import json
import os
import pathlib
from dataclasses import dataclass, field


@dataclass
class DatabaseConfig:
    host: str = "localhost"
    port: int = 5432
    name: str = "lms"
    user: str = "lms"
    password: str = ""

    @property
    def conninfo(self) -> str:
        return (
            f"host={self.host} port={self.port} "
            f"dbname={self.name} user={self.user} password={self.password}"
        )


@dataclass
class AppConfig:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)

    @classmethod
    def load(cls) -> "AppConfig":
        config_path = os.environ.get("CONFIG_FILE", "/run/secrets/config.json")
        path = pathlib.Path(config_path)

        if path.exists():
            with open(path) as f:
                data = json.load(f)
            db_data = data.get("database", {})
            return cls(database=DatabaseConfig(**db_data))

        print(f"Warning: Config file not found at {config_path}")
        return cls()
