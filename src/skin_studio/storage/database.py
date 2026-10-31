"""SQLite connection and schema migration management."""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from skin_studio.storage.migrations.v0001 import upgrade as upgrade_v1
from skin_studio.storage.migrations.v0002 import upgrade as upgrade_v2
from skin_studio.storage.migrations.v0003 import upgrade as upgrade_v3

LATEST_SCHEMA_VERSION = 3


def connect_database(path: Path) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=5.0)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    try:
        migrate(connection)
    except Exception:
        connection.close()
        raise
    return connection


def migrate(connection: sqlite3.Connection) -> None:
    current_version = int(connection.execute("PRAGMA user_version").fetchone()[0])
    if current_version > LATEST_SCHEMA_VERSION:
        raise RuntimeError("Database schema is newer than this application")
    migrations = {1: upgrade_v1, 2: upgrade_v2, 3: upgrade_v3}
    for version in range(current_version + 1, LATEST_SCHEMA_VERSION + 1):
        migration = migrations.get(version)
        if migration is None:
            raise RuntimeError(f"Missing database migration {version}")
        try:
            connection.execute("BEGIN")
            migration(connection)
            connection.execute(f"PRAGMA user_version = {version}")
            connection.commit()
        except Exception:
            connection.rollback()
            raise


def integrity_check(connection: sqlite3.Connection) -> bool:
    result = connection.execute("PRAGMA integrity_check").fetchone()
    return result is not None and result[0] == "ok"


@contextmanager
def database(path: Path) -> Iterator[sqlite3.Connection]:
    connection = connect_database(path)
    try:
        yield connection
    finally:
        connection.close()
