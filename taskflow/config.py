"""Application configuration loaded from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
import re
from typing import Mapping


_ENV_KEY = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_dotenv(
    path: Path | None = None,
    environ: dict[str, str] | None = None,
) -> None:
    """Load simple KEY=VALUE entries without overwriting existing variables."""
    target = os.environ if environ is None else environ
    env_path = (
        Path(__file__).resolve().parent.parent / ".env"
        if path is None
        else path
    )
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return
    except OSError as exc:
        raise ValueError(f"Unable to read environment file: {env_path}") from exc

    for line_number, raw_line in enumerate(lines, start=1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, separator, value = line.partition("=")
        key = key.strip()
        if not separator or not _ENV_KEY.fullmatch(key):
            raise ValueError(
                f"Invalid environment entry on line {line_number} of {env_path}."
            )
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        target.setdefault(key, value)


@dataclass(frozen=True)
class Config:
    telegram_bot_token: str
    mysql_host: str
    mysql_port: int
    mysql_database: str
    mysql_user: str
    mysql_password: str
    mysql_pool_name: str = "taskflow_pool"
    mysql_pool_size: int = 5

    @classmethod
    def from_env(cls, environ: Mapping[str, str] | None = None) -> Config:
        if environ is None:
            load_dotenv()
            env: Mapping[str, str] = os.environ
        else:
            env = environ
        required = (
            "TELEGRAM_BOT_TOKEN",
            "MYSQL_HOST",
            "MYSQL_DATABASE",
            "MYSQL_USER",
        )
        missing = [name for name in required if not env.get(name, "").strip()]
        if missing:
            raise ValueError(
                "Missing required environment variables: " + ", ".join(missing)
            )

        try:
            mysql_port = int(env.get("MYSQL_PORT", "3306"))
        except ValueError as exc:
            raise ValueError("MYSQL_PORT must be an integer.") from exc
        if not 1 <= mysql_port <= 65535:
            raise ValueError("MYSQL_PORT must be between 1 and 65535.")

        try:
            pool_size = int(env.get("MYSQL_POOL_SIZE", "5"))
        except ValueError as exc:
            raise ValueError("MYSQL_POOL_SIZE must be an integer.") from exc
        if not 1 <= pool_size <= 32:
            raise ValueError("MYSQL_POOL_SIZE must be between 1 and 32.")

        return cls(
            telegram_bot_token=env["TELEGRAM_BOT_TOKEN"].strip(),
            mysql_host=env["MYSQL_HOST"].strip(),
            mysql_port=mysql_port,
            mysql_database=env["MYSQL_DATABASE"].strip(),
            mysql_user=env["MYSQL_USER"].strip(),
            mysql_password=env.get("MYSQL_PASSWORD", ""),
            mysql_pool_size=pool_size,
        )
