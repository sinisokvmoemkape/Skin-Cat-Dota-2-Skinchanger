from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from skin_studio.services.database_backup import create_database_backup
from skin_studio.storage.database import connect_database
from skin_studio.ui.widgets.database_backup_dialog import DatabaseBackupDialog


def test_backup_dialog_exports_application_database(qapp, tmp_path: Path, monkeypatch) -> None:
    qapp.processEvents()
    database_path = tmp_path / "skin-studio.sqlite3"
    backup_path = tmp_path / "exports" / "manual-backup.zip"

    def select_backup_path(parent, title, directory, file_filter):
        del parent, title, directory, file_filter
        return str(backup_path), ""

    connection = connect_database(database_path)
    dialog = DatabaseBackupDialog(None, connection, database_path)
    monkeypatch.setattr(
        "skin_studio.ui.widgets.database_backup_dialog.QFileDialog.getSaveFileName",
        select_backup_path,
    )
    try:
        dialog._export_backup()
        assert backup_path.is_file()
        assert dialog.status.text() == f"Backup created: {backup_path}"
    finally:
        dialog.close()
        connection.close()


def test_backup_dialog_previews_and_restores_after_confirmation(
    qapp, tmp_path: Path, monkeypatch
) -> None:
    qapp.processEvents()
    database_path = tmp_path / "skin-studio.sqlite3"
    backup_path = tmp_path / "manual-backup.zip"
    connection = connect_database(database_path)
    connection.execute(
        "INSERT INTO local_selection_items(item_id) VALUES (?)", ("sample-courier",)
    )
    connection.commit()
    create_database_backup(connection, backup_path, database_path)
    connection.execute(
        "DELETE FROM local_selection_items WHERE item_id = ?", ("sample-courier",)
    )
    connection.commit()

    def select_backup_path(parent, title, directory, file_filter):
        del parent, title, directory, file_filter
        return str(backup_path), ""

    def confirm_restore(parent, title, text, buttons, default_button):
        del parent, title, text, buttons, default_button
        return QMessageBox.StandardButton.Yes

    dialog = DatabaseBackupDialog(None, connection, database_path)
    monkeypatch.setattr(
        "skin_studio.ui.widgets.database_backup_dialog.QFileDialog.getOpenFileName",
        select_backup_path,
    )
    monkeypatch.setattr(
        "skin_studio.ui.widgets.database_backup_dialog.QMessageBox.question",
        confirm_restore,
    )
    try:
        dialog._select_backup()
        assert connection.execute(
            "SELECT item_id FROM local_selection_items"
        ).fetchone()[0] == "sample-courier"
        assert dialog.status.text() == "Application data restored."
        assert dialog._preview is None
    finally:
        dialog.close()
        connection.close()


def test_backup_dialog_does_not_restore_without_confirmation(
    qapp, tmp_path: Path, monkeypatch
) -> None:
    qapp.processEvents()
    database_path = tmp_path / "skin-studio.sqlite3"
    backup_path = tmp_path / "manual-backup.zip"
    connection = connect_database(database_path)
    connection.execute(
        "INSERT INTO local_selection_items(item_id) VALUES (?)", ("sample-courier",)
    )
    connection.commit()
    create_database_backup(connection, backup_path, database_path)
    connection.execute(
        "DELETE FROM local_selection_items WHERE item_id = ?", ("sample-courier",)
    )
    connection.commit()

    def select_backup_path(parent, title, directory, file_filter):
        del parent, title, directory, file_filter
        return str(backup_path), ""

    def decline_restore(parent, title, text, buttons, default_button):
        del parent, title, text, buttons, default_button
        return QMessageBox.StandardButton.No

    dialog = DatabaseBackupDialog(None, connection, database_path)
    monkeypatch.setattr(
        "skin_studio.ui.widgets.database_backup_dialog.QFileDialog.getOpenFileName",
        select_backup_path,
    )
    monkeypatch.setattr(
        "skin_studio.ui.widgets.database_backup_dialog.QMessageBox.question",
        decline_restore,
    )
    try:
        dialog._select_backup()
        assert connection.execute(
            "SELECT COUNT(*) FROM local_selection_items"
        ).fetchone()[0] == 0
        assert dialog._preview is not None
    finally:
        dialog.close()
        connection.close()
