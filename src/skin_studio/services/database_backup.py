"""Integrity-checked backup and restore for Skin Cat's SQLite database only."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tempfile
import zipfile
import zlib
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from skin_studio import __version__
from skin_studio.storage.database import LATEST_SCHEMA_VERSION, integrity_check

_FORMAT_VERSION = 1
_DATABASE_MEMBER = "database.sqlite3"
_MANIFEST_MEMBER = "manifest.json"
_MAX_MANIFEST_BYTES = 16 * 1024
_MAX_DATABASE_BYTES = 512 * 1024 * 1024
_COPY_CHUNK_BYTES = 1024 * 1024


class DatabaseBackupError(Exception):
    """A backup or restore operation failed with a safe displayable code."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass
class BackupPreview:
    source_path: Path
    created_at: str
    schema_version: int
    catalog_items: int
    local_selection_items: int
    favorites: int
    legacy_profiles: int
    database_path: Path
    _temporary_directory: tempfile.TemporaryDirectory[str]

    def cleanup(self) -> None:
        self._temporary_directory.cleanup()


def create_database_backup(
    connection: sqlite3.Connection, output_path: Path, current_database_path: Path
) -> None:
    """Write an atomic zip backup containing only a consistent database snapshot."""
    output_path = output_path.expanduser().absolute()
    if output_path.resolve() == current_database_path.resolve():
        raise DatabaseBackupError("invalid_destination")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.exists() and output_path.is_dir():
        raise DatabaseBackupError("invalid_destination")

    temporary_directory: tempfile.TemporaryDirectory[str] | None = None
    archive_path: Path | None = None
    try:
        temporary_directory = tempfile.TemporaryDirectory(prefix="skin-cat-backup-")
        temporary_root = Path(temporary_directory.name)
        snapshot_path = temporary_root / _DATABASE_MEMBER
        descriptor, archive_name = tempfile.mkstemp(
            prefix=".skin-cat-backup-", suffix=".tmp", dir=output_path.parent
        )
        os.close(descriptor)
        archive_file = Path(archive_name)
        archive_path = archive_file
        snapshot = sqlite3.connect(snapshot_path)
        try:
            connection.backup(snapshot)
            if not integrity_check(snapshot):
                raise DatabaseBackupError("database_integrity_failed")
        finally:
            snapshot.close()

        digest, database_size = _sha256_file(snapshot_path)
        if database_size > _MAX_DATABASE_BYTES:
            raise DatabaseBackupError("database_too_large")
        manifest = {
            "format_version": _FORMAT_VERSION,
            "application_version": __version__,
            "created_at": datetime.now(UTC).isoformat(),
            "schema_version": LATEST_SCHEMA_VERSION,
            "database_size": database_size,
            "database_sha256": digest,
        }
        with zipfile.ZipFile(archive_file, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot_path, _DATABASE_MEMBER)
            archive.writestr(
                _MANIFEST_MEMBER,
                json.dumps(manifest, separators=(",", ":"), sort_keys=True),
            )
        os.chmod(archive_file, 0o600)
        os.replace(archive_file, output_path)
    except DatabaseBackupError:
        raise
    except (OSError, sqlite3.Error, zipfile.BadZipFile, zlib.error, RuntimeError) as error:
        raise DatabaseBackupError("backup_failed") from error
    finally:
        if temporary_directory is not None:
            temporary_directory.cleanup()
        if archive_path is not None:
            archive_path.unlink(missing_ok=True)


def inspect_database_backup(path: Path) -> BackupPreview:
    """Validate a backup completely and retain a staged DB for restore preview."""
    temporary_directory: tempfile.TemporaryDirectory[str] | None = None
    try:
        temporary_directory = tempfile.TemporaryDirectory(prefix="skin-cat-restore-")
        database_path = Path(temporary_directory.name) / _DATABASE_MEMBER
        with zipfile.ZipFile(path) as archive:
            members = archive.infolist()
            names = [member.filename for member in members]
            if sorted(names) != sorted((_DATABASE_MEMBER, _MANIFEST_MEMBER)):
                raise DatabaseBackupError("invalid_backup")
            database_member = archive.getinfo(_DATABASE_MEMBER)
            manifest_member = archive.getinfo(_MANIFEST_MEMBER)
            if (
                database_member.file_size > _MAX_DATABASE_BYTES
                or manifest_member.file_size > _MAX_MANIFEST_BYTES
            ):
                raise DatabaseBackupError("backup_too_large")
            manifest = json.loads(archive.read(_MANIFEST_MEMBER))
            _validate_manifest(manifest, database_member.file_size)
            digest = hashlib.sha256()
            copied = 0
            with archive.open(_DATABASE_MEMBER) as source, database_path.open("wb") as target:
                while chunk := source.read(_COPY_CHUNK_BYTES):
                    copied += len(chunk)
                    if copied > _MAX_DATABASE_BYTES:
                        raise DatabaseBackupError("backup_too_large")
                    digest.update(chunk)
                    target.write(chunk)
        if copied != manifest["database_size"] or digest.hexdigest() != manifest["database_sha256"]:
            raise DatabaseBackupError("backup_checksum_failed")
        counts = _read_database_counts(database_path)
        return BackupPreview(
            source_path=path,
            created_at=manifest["created_at"],
            schema_version=manifest["schema_version"],
            database_path=database_path,
            _temporary_directory=temporary_directory,
            **counts,
        )
    except DatabaseBackupError:
        if temporary_directory is not None:
            temporary_directory.cleanup()
        raise
    except (
        OSError,
        ValueError,
        TypeError,
        KeyError,
        zipfile.BadZipFile,
        json.JSONDecodeError,
        sqlite3.Error,
        RuntimeError,
        NotImplementedError,
        zlib.error,
    ) as error:
        if temporary_directory is not None:
            temporary_directory.cleanup()
        raise DatabaseBackupError("invalid_backup") from error


def read_database_counts(connection: sqlite3.Connection) -> dict[str, int]:
    if not integrity_check(connection):
        raise DatabaseBackupError("database_integrity_failed")
    if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
        raise DatabaseBackupError("database_integrity_failed")
    return {
        "catalog_items": _count_rows(connection, "cosmetic_items"),
        "local_selection_items": _count_rows(connection, "local_selection_items"),
        "favorites": _count_rows(connection, "cosmetic_favorites"),
        "legacy_profiles": _count_rows(connection, "profiles"),
    }


def restore_database_backup(
    connection: sqlite3.Connection,
    preview: BackupPreview,
    current_database_path: Path,
) -> None:
    """Revalidate then restore atomically in the live connection with rollback backup."""
    if preview.source_path.resolve() == current_database_path.resolve():
        raise DatabaseBackupError("invalid_backup")

    fresh_preview = inspect_database_backup(preview.source_path)
    current_copy_path: Path | None = None
    try:
        descriptor, current_copy_name = tempfile.mkstemp(
            prefix="skin-cat-before-restore-", suffix=".sqlite3"
        )
        os.close(descriptor)
        current_copy_path = Path(current_copy_name)
        safety_copy = sqlite3.connect(current_copy_path)
        try:
            connection.backup(safety_copy)
        finally:
            safety_copy.close()

        source = sqlite3.connect(f"file:{fresh_preview.database_path}?mode=ro", uri=True)
        try:
            source.backup(connection)
            if not integrity_check(connection):
                raise DatabaseBackupError("database_integrity_failed")
            if connection.execute("PRAGMA foreign_key_check").fetchone() is not None:
                raise DatabaseBackupError("database_integrity_failed")
        except Exception:
            rollback = sqlite3.connect(current_copy_path)
            try:
                rollback.backup(connection)
            except sqlite3.Error as error:
                raise DatabaseBackupError("restore_rollback_failed") from error
            finally:
                rollback.close()
            raise
        finally:
            source.close()
    except DatabaseBackupError:
        raise
    except (OSError, sqlite3.Error) as error:
        raise DatabaseBackupError("restore_failed") from error
    finally:
        if current_copy_path is not None:
            current_copy_path.unlink(missing_ok=True)
        fresh_preview.cleanup()


def _validate_manifest(manifest: Any, archive_database_size: int) -> None:
    if not isinstance(manifest, dict):
        raise DatabaseBackupError("invalid_backup")
    if manifest.get("format_version") != _FORMAT_VERSION:
        raise DatabaseBackupError("unsupported_backup")
    if manifest.get("schema_version") != LATEST_SCHEMA_VERSION:
        raise DatabaseBackupError("unsupported_backup")
    if (
        isinstance(manifest.get("database_size"), bool)
        or manifest.get("database_size") != archive_database_size
        or not isinstance(manifest.get("database_size"), int)
    ):
        raise DatabaseBackupError("invalid_backup")
    digest = manifest.get("database_sha256")
    if not isinstance(digest, str) or len(digest) != 64:
        raise DatabaseBackupError("invalid_backup")
    created_at = manifest.get("created_at")
    if not isinstance(created_at, str):
        raise DatabaseBackupError("invalid_backup")
    datetime.fromisoformat(created_at)


def _read_database_counts(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    try:
        if int(connection.execute("PRAGMA user_version").fetchone()[0]) != LATEST_SCHEMA_VERSION:
            raise DatabaseBackupError("unsupported_backup")
        return read_database_counts(connection)
    finally:
        connection.close()


def _count_rows(connection: sqlite3.Connection, table: str) -> int:
    allowed_tables = {
        "cosmetic_items",
        "local_selection_items",
        "cosmetic_favorites",
        "profiles",
    }
    if table not in allowed_tables:
        raise ValueError("Unsupported table")
    return int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])


def _sha256_file(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(_COPY_CHUNK_BYTES):
            size += len(chunk)
            digest.update(chunk)
    return digest.hexdigest(), size
