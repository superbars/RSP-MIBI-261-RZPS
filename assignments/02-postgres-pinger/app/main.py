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

import psycopg


class DatabaseConfig(TypedDict):
    host: str
    port: int
    dbname: str
    connect_timeout: int
    statement_timeout_ms: int


CONFIG_PATH = Path(__file__).with_name("config.toml")
EXPECTED_CONFIG_KEYS = {
    "host",
    "port",
    "dbname",
    "connect_timeout",
    "statement_timeout_ms",
}
EXPECTED_MAJOR_VERSIONS = {18}
STOP_EVENT = threading.Event()


class MaximumLevelFilter(logging.Filter):
    """Фильтр записей"""

    def __init__(self, maximum_level: int) -> None:
        super().__init__()
        self.maximum_level = maximum_level

    def filter(self, record: logging.LogRecord) -> bool:
        return record.levelno <= self.maximum_level


def configure_logging(log_file: str | None) -> logging.Logger:
    """Направить сообщения в stdout, ошибки в stderr и в файл"""
    logger = logging.getLogger("postgres-pinger")
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
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def load_config(path: Path = CONFIG_PATH) -> DatabaseConfig:
    with path.open("rb") as config_file:
        raw = tomllib.load(config_file)

    unknown = set(raw) - EXPECTED_CONFIG_KEYS
    missing = EXPECTED_CONFIG_KEYS - set(raw)
    if unknown:
        raise ValueError("Unknown config keys: " + ", ".join(sorted(unknown)))
    if missing:
        raise ValueError("Missing config keys: " + ", ".join(sorted(missing)))

    for key in ("host", "dbname"):
        if not isinstance(raw[key], str) or not raw[key].strip():
            raise ValueError(f"{key} must be a non-empty string")
    for key, minimum, maximum in (
        ("port", 1, 65535),
        ("connect_timeout", 1, 60),
        ("statement_timeout_ms", 1, 60_000),
    ):
        value = raw[key]
        if not isinstance(value, int) or isinstance(value, bool) or not minimum <= value <= maximum:
            raise ValueError(f"{key} must be an integer from {minimum} to {maximum}")

    return raw  # type: ignore[return-value]


def load_environment() -> tuple[str, str, int, str | None]:
    user = os.environ.get("DB_USER", "")
    password = os.environ.get("DB_PASSWORD", "")
    interval_text = os.environ.get("POLL_INTERVAL_SECONDS", "")
    log_file = os.environ.get("LOG_FILE") or None

    if not user:
        raise ValueError("DB_USER is required")
    if not password:
        raise ValueError("DB_PASSWORD is required")
    try:
        interval = int(interval_text)
    except ValueError as error:
        raise ValueError("POLL_INTERVAL_SECONDS must be an integer") from error
    if interval < 1:
        raise ValueError("POLL_INTERVAL_SECONDS must be at least 1")

    return user, password, interval, log_file


def check_database(
    config: DatabaseConfig,
    user: str,
    password: str,
    logger: logging.Logger,
) -> None:
    started_at = time.monotonic()
    try:
        with psycopg.connect(
            host=config["host"],
            port=config["port"],
            dbname=config["dbname"],
            user=user,
            password=password,
            connect_timeout=config["connect_timeout"],
            options=f"-c statement_timeout={config['statement_timeout_ms']}",
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

        logger.info(
            "Database connection succeeded in %d ms: %s",
            elapsed_ms,
            response,
        )
    except psycopg.Error as error:
        logger.error("Database connection failed: %s", error)
    except Exception:
        logger.exception("Unexpected error during database check")


def parse_postgres_major_version(response: str) -> int | None:
    prefix = "PostgreSQL "
    if not response.startswith(prefix):
        return None
    version = response[len(prefix) :].split(maxsplit=1)[0]
    major = version.split(".", maxsplit=1)[0]
    return int(major) if major.isdigit() else None


def request_stop(signum: int, _frame: object) -> None:
    del signum
    STOP_EVENT.set()


def run() -> int:
    try:
        config = load_config()
        user, password, interval, log_file = load_environment()
        logger = configure_logging(log_file)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as error:
        print(f"Configuration error: {error}", file=sys.stderr, flush=True)
        return 2

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    logger.info("PostgreSQL pinger started; interval=%d seconds", interval)

    while not STOP_EVENT.is_set():
        check_database(config, user, password, logger)
        STOP_EVENT.wait(interval)

    logger.info("PostgreSQL pinger stopped")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
