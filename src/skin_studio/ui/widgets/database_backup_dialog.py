"""User-data database backup and restore with a validated preview."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from skin_studio.i18n.manager import LanguageManager
from skin_studio.services.database_backup import (
    BackupPreview,
    DatabaseBackupError,
    create_database_backup,
    inspect_database_backup,
    read_database_counts,
    restore_database_backup,
)


def tr(source: str) -> str:
    return LanguageManager.text(source)


class DatabaseBackupDialog(QDialog):
    restored = Signal()

    def __init__(
        self,
        parent: QWidget | None,
        connection: sqlite3.Connection,
        database_path: Path,
    ) -> None:
        super().__init__(parent)
        self._connection = connection
        self._database_path = database_path
        self._preview: BackupPreview | None = None
        self.setMinimumWidth(520)

        layout = QVBoxLayout(self)
        self.title = QLabel()
        self.title.setObjectName("sectionTitle")
        self.description = QLabel()
        self.description.setWordWrap(True)
        actions = QHBoxLayout()
        self.export_button = QPushButton()
        self.export_button.setObjectName("primaryButton")
        self.export_button.clicked.connect(self._export_backup)
        self.restore_button = QPushButton()
        self.restore_button.clicked.connect(self._select_backup)
        actions.addWidget(self.export_button)
        actions.addWidget(self.restore_button)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.buttons = QPushButton()
        self.buttons.clicked.connect(self.accept)
        layout.addWidget(self.title)
        layout.addWidget(self.description)
        layout.addLayout(actions)
        layout.addWidget(self.status)
        layout.addWidget(self.buttons, 0)
        self.retranslate()

    def retranslate(self) -> None:
        self.setWindowTitle(tr("Application data backup"))
        self.title.setText(tr("Application data backup"))
        self.description.setText(
            tr(
                "Backups contain only Skin Cat's local database. Steam and Dota 2 files, "
                "settings, and logs are not included."
            )
        )
        self.export_button.setText(tr("Create backup…"))
        self.restore_button.setText(tr("Preview and restore…"))
        self.buttons.setText(tr("Close"))

    @Slot()
    def _export_backup(self) -> None:
        filename, _ = QFileDialog.getSaveFileName(
            self,
            tr("Save Skin Cat backup"),
            str(Path.home() / "skin-cat-backup.zip"),
            tr("Skin Cat backup (*.zip)"),
        )
        if not filename:
            return
        backup_path = Path(filename)
        if backup_path.suffix.casefold() != ".zip":
            backup_path = backup_path.with_suffix(".zip")
        try:
            create_database_backup(self._connection, backup_path, self._database_path)
        except DatabaseBackupError as error:
            self.status.setText(_backup_error_message(error.code))
            return
        self.status.setText(tr("Backup created: {path}").format(path=backup_path))

    @Slot()
    def _select_backup(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(
            self,
            tr("Select Skin Cat backup"),
            str(Path.home()),
            tr("Skin Cat backup (*.zip)"),
        )
        if not filename:
            return

        self._cleanup_preview()
        try:
            preview = inspect_database_backup(Path(filename))
        except DatabaseBackupError as error:
            self.status.setText(_backup_error_message(error.code))
            return
        self._preview = preview
        try:
            current_counts = read_database_counts(self._connection)
        except DatabaseBackupError as error:
            self.status.setText(_backup_error_message(error.code))
            self._cleanup_preview()
            return
        self.status.setText(_preview_description(preview, current_counts))
        answer = QMessageBox.question(
            self,
            tr("Restore application data?"),
            tr(
                "This will replace the current Skin Cat database with the validated backup. "
                "Steam and Dota 2 files will not be changed. Continue?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        try:
            restore_database_backup(self._connection, preview, self._database_path)
        except DatabaseBackupError as error:
            self.status.setText(_backup_error_message(error.code))
            return
        self.status.setText(tr("Application data restored."))
        self.restored.emit()
        self._cleanup_preview()

    def _cleanup_preview(self) -> None:
        if self._preview is not None:
            self._preview.cleanup()
            self._preview = None

    def closeEvent(self, event: QCloseEvent) -> None:
        self._cleanup_preview()
        super().closeEvent(event)


def _preview_description(preview: BackupPreview, current_counts: dict[str, int]) -> str:
    return tr(
        "Validated backup from {created_at}\n"
        "Catalog entries (current → backup): {current_catalog} → {backup_catalog}\n"
        "Items in local selection (current → backup): {current_selection} → {backup_selection}\n"
        "Favorites (current → backup): {current_favorites} → {backup_favorites}\n"
        "Legacy profiles (current → backup): {current_profiles} → {backup_profiles}\n"
        "Restoring replaces the current Skin Cat database."
    ).format(
        created_at=preview.created_at,
        current_catalog=current_counts["catalog_items"],
        backup_catalog=preview.catalog_items,
        current_selection=current_counts["local_selection_items"],
        backup_selection=preview.local_selection_items,
        current_favorites=current_counts["favorites"],
        backup_favorites=preview.favorites,
        current_profiles=current_counts["legacy_profiles"],
        backup_profiles=preview.legacy_profiles,
    )


def _backup_error_message(code: str) -> str:
    messages = {
        "invalid_destination": "Choose a separate backup file, not the live database.",
        "database_integrity_failed": "Database integrity check failed; no data was restored.",
        "database_too_large": "The database exceeds the supported backup size.",
        "backup_too_large": "The selected backup exceeds the supported size.",
        "backup_checksum_failed": "The selected backup failed its integrity check.",
        "unsupported_backup": "The selected backup format or schema is not supported.",
        "invalid_backup": "The selected file is not a valid Skin Cat backup.",
        "backup_failed": "Could not create the backup file.",
        "restore_failed": "Could not restore the backup; the current database was preserved.",
        "restore_rollback_failed": (
            "Restore and rollback both failed. Do not restart the app; preserve the database "
            "file and contact support."
        ),
    }
    return tr(messages.get(code, "The backup operation failed."))
