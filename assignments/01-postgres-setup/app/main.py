import getpass
import re
import sys
import tomllib
from pathlib import Path
from typing import TypedDict
#import requests

import psycopg # For connetction to DB 
from psycopg import sql

from __future__ import annotations


class DatabaseConfig(TypedDict):
    host: str
    port: int
    dbname: str
    connect_timeout: int


CONFIG_PATH = Path(__file__).with_name("config.toml")
EXPECTED_CONFIG_KEYS = {"host", "port", "dbname", "connect_timeout"}
LOGIN_PATTERN = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,62}\Z")


def load_config(path: Path = CONFIG_PATH) -> DatabaseConfig:
    """Читаем и используем, только определенные параметры подключения (из томл файла)"""
    with path.open("rb") as config_file:
        raw_config = tomllib.load(config_file)

    unknown_keys = set(raw_config) - EXPECTED_CONFIG_KEYS
    missing_keys = EXPECTED_CONFIG_KEYS - set(raw_config)
    if unknown_keys:
        raise ValueError(
            "Troubles in config.toml: "
            + ", ".join(sorted(unknown_keys))
        )
    if missing_keys:
        raise ValueError(
            "Troubles in config.toml: "
            + ", ".join(sorted(missing_keys))
        )

    host = raw_config["host"]
    port = raw_config["port"]
    dbname = raw_config["dbname"]
    connect_timeout = raw_config["connect_timeout"]

    if not isinstance(host, str) or not host.strip():
        raise ValueError("host must be not empty")
    if not isinstance(port, int) or isinstance(port, bool) or not 1 <= port <= 65535:
        raise ValueError("port troubles")
    if not isinstance(dbname, str) or not dbname.strip():
        raise ValueError("db troubles")
    if (
        not isinstance(connect_timeout, int)
        or isinstance(connect_timeout, bool)
        or not 1 <= connect_timeout <= 60
    ):
        raise ValueError("connect_timeout from 1 to 60")

    return {
        "host": host,
        "port": port,
        "dbname": dbname,
        "connect_timeout": connect_timeout,
    }


def read_credentials() -> tuple[str, str]:
    """Запросить креды, не отображая пароль"""
    login = input("Login: ").strip()
    if not LOGIN_PATTERN.fullmatch(login):
        raise ValueError(
            "Invalid login or you are trying some kinda SQLi "
        )

    password = getpass.getpass("Password from app: ")
    if not password:
        raise ValueError("Empty password")
    return login, password


def query_server_version(
    config: DatabaseConfig, login: str, password: str
) -> str:
    """Подключиться с раздельными параметрами и выполнить запрос."""
    with psycopg.connect( 
        host=config["host"],
        port=config["port"],
        dbname=config["dbname"],
        user=login,
        password=password,
        connect_timeout=config["connect_timeout"],
    ) as connection:
        with connection.cursor() as cursor:
            """Сам запрос SELECT VERSION();"""
            cursor.execute(sql.SQL("SELECT VERSION();"))
            row = cursor.fetchone()

    if row is None:
        raise RuntimeError("Some troubles with version????")
    return str(row[0])


def main() -> int:
    try:
        config = load_config()
        login, password = read_credentials()
        version = query_server_version(config, login, password)
    except (OSError, ValueError, tomllib.TOMLDecodeError) as error:
        print(f"Error in input: {error}", file=sys.stderr)
        return 2
    except psycopg.Error as error:
        print(f"Error in connection: {error}", file=sys.stderr)
        return 1

    print(f"Version of server check please: {version}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

