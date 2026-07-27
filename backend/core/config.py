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
class EncryptionConfig:
    vault_key: str = ""


@dataclass
class SessionConfig:
    secret_key: str = ""
    expire_minutes: int = 1440  # 24 hours
    secure_cookie: bool = False  # Set True in production
    remember_days: int = 60  # Remember-me device token lifetime
    remember_cookie_name: str = "remember_token"


@dataclass
class SmtpConfig:
    host: str = "localhost"
    port: int = 587
    username: str = ""
    password: str = ""
    from_address: str = ""
    use_tls: bool = True


@dataclass
class AppConfig:
    database: DatabaseConfig = field(default_factory=DatabaseConfig)
    encryption: EncryptionConfig = field(default_factory=EncryptionConfig)
    session: SessionConfig = field(default_factory=SessionConfig)
    smtp: SmtpConfig = field(default_factory=SmtpConfig)
    app_base_url: str = "http://localhost:4200"

    def validate(self) -> None:
        """Raise if any secret needed to run safely is missing.

        The dataclass defaults are empty strings, so a missing or partial config
        file would otherwise start the app with an empty JWT signing key - which
        lets anyone mint a password reset token - or with vault encryption
        silently disabled.
        """
        missing = []

        if not self.session.secret_key:
            missing.append("session.secret_key")

        if not self.encryption.vault_key:
            missing.append("encryption.vault_key")

        if missing:
            raise ValueError(
                f"Config is missing required secrets: {', '.join(missing)}. "
                "Set them in the config file (see secrets/config.example.json)."
            )

    @classmethod
    def load(cls) -> "AppConfig":
        config_path = os.environ.get("CONFIG_FILE", "/run/secrets/config.json")
        path = pathlib.Path(config_path)

        if not path.exists():
            raise FileNotFoundError(f"Config file not found at {config_path}")

        with open(path) as f:
            data = json.load(f)
        db_data = data.get("database", {})
        enc_data = data.get("encryption", {})
        session_data = data.get("session", {})
        smtp_data = data.get("smtp", {})
        config = cls(
            database=DatabaseConfig(**db_data),
            encryption=EncryptionConfig(**enc_data),
            session=SessionConfig(**session_data),
            smtp=SmtpConfig(**smtp_data),
            app_base_url=data.get("app_base_url", "http://localhost:4200"),
        )
        config.validate()
        return config
