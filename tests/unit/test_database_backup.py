import json
import os
import stat
import tempfile
import zipfile
from pathlib import Path

import pytest

from skin_studio.services.database_backup import (
    BackupPreview,
    DatabaseBackupError,
    create_database_backup,
    inspect_database_backup,
    restore_database_backup,
)
from skin_studio.storage.database import connect_database


def test_backup_preview_and_restore_round_trip_only_application_database(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "app" / "skin-studio.sqlite3"
    backup_path = tmp_path / "exports" / "backup.zip"
    connection = connect_database(database_path)
    try:
        connection.execute(
            "INSERT INTO local_selection_items(item_id) VALUES (?)", ("sample-courier",)
        )
        connection.commit()
        create_database_backup(connection, backup_path, database_path)
        if os.name == "posix":
            assert stat.S_IMODE(backup_path.stat().st_mode) == 0o600

        connection.execute(
            "DELETE FROM local_selection_items WHERE item_id = ?", ("sample-courier",)
        )
        connection.commit()
        preview = inspect_database_backup(backup_path)
        try:
            assert preview.schema_version == 3
            assert preview.catalog_items == 11
            assert preview.local_selection_items == 1
            assert preview.favorites == 0
            assert preview.legacy_profiles == 0
            restore_database_backup(connection, preview, database_path)
        finally:
            preview.cleanup()

        restored = connection.execute(
            "SELECT item_id FROM local_selection_items"
        ).fetchall()
        assert [row[0] for row in restored] == ["sample-courier"]
        assert not database_path.parent.joinpath("steamapps").exists()
    finally:
        connection.close()


def test_backup_refuses_the_live_database_as_destination(tmp_path: Path) -> None:
    database_path = tmp_path / "skin-studio.sqlite3"
    connection = connect_database(database_path)
    try:
        with pytest.raises(DatabaseBackupError, match="invalid_destination"):
            create_database_backup(connection, database_path, database_path)
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    finally:
        connection.close()


def test_preview_rejects_changed_database_bytes(tmp_path: Path) -> None:
    database_path = tmp_path / "skin-studio.sqlite3"
    backup_path = tmp_path / "backup.zip"
    connection = connect_database(database_path)
    try:
        create_database_backup(connection, backup_path, database_path)
    finally:
        connection.close()

    corrupted_path = tmp_path / "corrupted.zip"
    with zipfile.ZipFile(backup_path) as source, zipfile.ZipFile(corrupted_path, "w") as target:
        database_bytes = bytearray(source.read("database.sqlite3"))
        database_bytes[-1] ^= 0x01
        target.writestr("database.sqlite3", database_bytes)
        target.writestr("manifest.json", source.read("manifest.json"))

    with pytest.raises(DatabaseBackupError, match="backup_checksum_failed"):
        inspect_database_backup(corrupted_path)


def test_preview_rejects_unknown_archive_members(tmp_path: Path) -> None:
    backup_path = tmp_path / "invalid.zip"
    with zipfile.ZipFile(backup_path, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"format_version": 1}))
        archive.writestr("../outside.txt", "not allowed")

    with pytest.raises(DatabaseBackupError, match="invalid_backup"):
        inspect_database_backup(backup_path)


def test_restore_revalidates_backup_after_preview(tmp_path: Path) -> None:
    database_path = tmp_path / "skin-studio.sqlite3"
    backup_path = tmp_path / "backup.zip"
    connection = connect_database(database_path)
    try:
        connection.execute(
            "INSERT INTO local_selection_items(item_id) VALUES (?)", ("sample-courier",)
        )
        connection.commit()
        create_database_backup(connection, backup_path, database_path)
        preview = inspect_database_backup(backup_path)
        try:
            with zipfile.ZipFile(backup_path, "w") as archive:
                archive.writestr("invalid.txt", "changed after preview")
            connection.execute(
                "DELETE FROM local_selection_items WHERE item_id = ?", ("sample-courier",)
            )
            connection.commit()

            with pytest.raises(DatabaseBackupError, match="invalid_backup"):
                restore_database_backup(connection, preview, database_path)
            assert connection.execute(
                "SELECT COUNT(*) FROM local_selection_items"
            ).fetchone()[0] == 0
        finally:
            preview.cleanup()
    finally:
        connection.close()


def test_restore_refuses_live_database_as_backup(tmp_path: Path) -> None:
    database_path = tmp_path / "skin-studio.sqlite3"
    temporary_directory = tempfile.TemporaryDirectory()
    preview = BackupPreview(
        source_path=database_path,
        created_at="2026-10-31T00:00:00+00:00",
        schema_version=3,
        catalog_items=0,
        local_selection_items=0,
        favorites=0,
        legacy_profiles=0,
        database_path=Path(temporary_directory.name) / "database.sqlite3",
        _temporary_directory=temporary_directory,
    )
    connection = connect_database(database_path)
    try:
        with pytest.raises(DatabaseBackupError, match="invalid_backup"):
            restore_database_backup(connection, preview, database_path)
        assert connection.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        assert connection.execute("SELECT COUNT(*) FROM cosmetic_items").fetchone()[0] == 11
    finally:
        preview.cleanup()
        connection.close()
