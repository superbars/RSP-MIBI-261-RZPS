from __future__ import annotations

import logging
import os
import signal
import sys
import threading
import time
import tomllib
from pathlib import Path
from typing import TypedDict

# python client for vault
import hvac
import psycopg
from hvac import exceptions as vault_exceptions


class DatabaseConfig(TypedDict):
    host: str
    port: int
    dbname: str
    connect_timeout: int
    statement_timeout_ms: int

# just conf dict
class VaultConfig(TypedDict):
    address: str
    role_id: str
    secret_id: str
    mount_point: str
    secret_path: str
    timeout: int


CONFIG_PATH = Path(__file__).with_name("config.toml")
EXPECTED_MAJOR_VERSIONS = {18}
STOP_EVENT = threading.Event()


class MaximumLevelFilter(logging.Filter):
    def __init__(self, maximum_level: int) -> None:
        super().__init__()
        self.maximum_level = maximum_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno <= self.maximum_level


def configure_logging(log_file: str | None) -> logging.Logger:
    logger = logging.getLogger("vault-postgres-pinger")
    logger.setLevel(logging.INFO)
    logger.handlers.clear()
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s %(levelname)s %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(logging.INFO)
    stdout_handler.addFilter(MaximumLevelFilter(logging.WARNING))
    stdout_handler.setFormatter(formatter)
    logger.addHandler(stdout_handler)

    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setLevel(logging.ERROR)
    stderr_handler.setFormatter(formatter)
    logger.addHandler(stderr_handler)

    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(path, encoding="utf-8")
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def require_environment(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"{name} is required")
    return value


def load_settings() -> tuple[DatabaseConfig, VaultConfig, int, str | None]:
    with CONFIG_PATH.open("rb") as config_file:
        raw = tomllib.load(config_file)

    database = raw.get("database")
    if not isinstance(database, dict):
        raise ValueError("[database] section is required in config.toml")

    config: DatabaseConfig = {
        "host": str(database["host"]),
        "port": int(database["port"]),
        "dbname": str(database["dbname"]),
        "connect_timeout": int(database["connect_timeout"]),
        "statement_timeout_ms": int(database["statement_timeout_ms"]),
    }

    interval = int(require_environment("POLL_INTERVAL_SECONDS"))
    if interval < 1:
        raise ValueError("POLL_INTERVAL_SECONDS must be at least 1")

# some envs are from compose and some from approle.env
    vault: VaultConfig = {
        "address": require_environment("VAULT_ADDR"),
        "role_id": require_environment("VAULT_ROLE_ID"),
        "secret_id": require_environment("VAULT_SECRET_ID"),
        # secret
        "mount_point": require_environment("VAULT_MOUNT_POINT"),
        # pinger/database, so the full path after that /secret/pinger/database
        "secret_path": require_environment("VAULT_SECRET_PATH"),
        "timeout": int(os.environ.get("VAULT_TIMEOUT_SECONDS", "5")),
    }

    return config, vault, interval, os.environ.get("LOG_FILE") or None


def read_database_credentials(vault: VaultConfig) -> tuple[str, str]:
    # use lib for vault python client 
    client = hvac.Client(url=vault["address"], timeout=vault["timeout"])

    # it sends request to /v1/auth/approle/login
    # hvac automatically saves token in cache
    client.auth.approle.login(
        role_id=vault["role_id"],
        secret_id=vault["secret_id"],
    )

    # it make request to /v1/secret/data/pinger/database to read secret
    # it also checks policy to read 
    response = client.secrets.kv.v2.read_secret_version(
        mount_point=vault["mount_point"],
        path=vault["secret_path"],
        # make exception for hvac.exceptions.InvalidPath if it doesn't find current version of secret
        raise_on_deleted_version=True,
    )

    # get secrets
    secret = response["data"]["data"]
    username = secret.get("username")
    password = secret.get("password")

    # check that fields are existing and they are not empty and they are strgins
    if not isinstance(username, str) or not username:
        raise ValueError("Vault secret does not contain a valid username")
    if not isinstance(password, str) or not password:
        raise ValueError("Vault secret does not contain a valid password")


    return username, password


def check_database(
    database: DatabaseConfig,
    vault: VaultConfig,
    logger: logging.Logger,
) -> None:
    started_at = time.monotonic()

    try:
        # The task requires reading the secret before every database request.
        user, password = read_database_credentials(vault)

        with psycopg.connect(
            host=database["host"],
            port=database["port"],
            dbname=database["dbname"],
            user=user,
            password=password,
            connect_timeout=database["connect_timeout"],
            options=f"-c statement_timeout={database['statement_timeout_ms']}",
        ) as connection:
            with connection.cursor() as cursor:
                cursor.execute("SELECT VERSION();")
                row = cursor.fetchone()

        response = None if row is None else row[0]
        elapsed_ms = round((time.monotonic() - started_at) * 1000)

        if not isinstance(response, str):
            logger.warning("Database returned an atypical version response: %r", response)
            return

        major_version = parse_postgres_major_version(response)
        if major_version not in EXPECTED_MAJOR_VERSIONS:
            logger.warning("Database returned an atypical version response: %s", response)
            return

        logger.info("Database connection succeeded in %d ms: %s", elapsed_ms, response)
    except (vault_exceptions.VaultError, ValueError, KeyError):
        logger.error("Could not obtain database credentials from Vault")
    except psycopg.Error:
        logger.error("Database connection failed; check the secret stored in Vault")
    except Exception:
        logger.exception("Unexpected error during database check")


def parse_postgres_major_version(response: str) -> int | None:
    prefix = "PostgreSQL "
    if not response.startswith(prefix):
        return None
    version = response[len(prefix) :].split(maxsplit=1)[0]
    major = version.split(".", maxsplit=1)[0]
    return int(major) if major.isdigit() else None


def request_stop(_signum: int, _frame: object) -> None:
    STOP_EVENT.set()


def run() -> int:
    try:
        database, vault, interval, log_file = load_settings()
        logger = configure_logging(log_file)
    except (OSError, ValueError, KeyError, tomllib.TOMLDecodeError) as error:
        print(f"Configuration error: {error}", file=sys.stderr, flush=True)
        return 2

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    logger.info("Vault PostgreSQL pinger started; interval=%d seconds", interval)

    # For read_database_credentials
    while not STOP_EVENT.is_set():
        check_database(database, vault, logger)
        STOP_EVENT.wait(interval)

    logger.info("Vault PostgreSQL pinger stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
