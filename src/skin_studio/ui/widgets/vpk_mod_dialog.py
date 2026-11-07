"""User-confirmed local VPK selection, replacement, and restore UI."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal, Slot
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from skin_studio.i18n.manager import LanguageManager
from skin_studio.services.vpk_mods import VpkBackup, VpkModError, VpkModService


def tr(source: str) -> str:
    return LanguageManager.text(source)


class _VpkOperationWorker(QObject):
    completed = Signal(object)
    failed = Signal(str)

    def __init__(self, operation: Callable[[], VpkBackup]) -> None:
        super().__init__()
        self._operation = operation

    @Slot()
    def run(self) -> None:
        try:
            self.completed.emit(self._operation())
        except (VpkModError, OSError) as exc:
            self.failed.emit(str(exc))


class VpkModDialog(QDialog):
    def __init__(
        self,
        parent: QWidget | None,
        *,
        backup_root: Path,
        is_game_running: Callable[[], bool],
        initial_game_root: Path | None = None,
    ) -> None:
        super().__init__(parent)
        self._backup_root = backup_root
        self._is_game_running = is_game_running
        self._game_root: Path | None = initial_game_root
        self._operation_thread: QThread | None = None
        self._operation_worker: _VpkOperationWorker | None = None
        self._operation_kind: str | None = None
        self.setMinimumWidth(620)

        layout = QVBoxLayout(self)
        self.title = QLabel()
        self.title.setObjectName("sectionTitle")
        layout.addWidget(self.title)
        self.warning = QLabel()
        self.warning.setObjectName("notice")
        self.warning.setWordWrap(True)
        layout.addWidget(self.warning)

        self.game_root_label = QLabel()
        self.game_root_path = QLineEdit()
        self.game_root_path.setReadOnly(True)
        self.browse_game_root_button = QPushButton()
        self.browse_game_root_button.clicked.connect(self._choose_game_root)

        self.source_label = QLabel()
        self.source_path = QLineEdit()
        self.source_path.setReadOnly(True)
        self.browse_source_button = QPushButton()
        self.browse_source_button.clicked.connect(self._choose_source)

        self.target_label = QLabel()
        self.target_path = QLineEdit()
        self.target_path.setReadOnly(True)
        self.browse_target_button = QPushButton()
        self.browse_target_button.clicked.connect(self._choose_target)

        for label, field, button in (
            (self.game_root_label, self.game_root_path, self.browse_game_root_button),
            (self.source_label, self.source_path, self.browse_source_button),
            (self.target_label, self.target_path, self.browse_target_button),
        ):
            row = QHBoxLayout()
            row.addWidget(field, 1)
            row.addWidget(button)
            layout.addWidget(label)
            layout.addLayout(row)

        self.apply_button = QPushButton()
        self.apply_button.setObjectName("primaryButton")
        self.apply_button.clicked.connect(self._apply)
        layout.addSpacing(8)
        layout.addWidget(self.apply_button)

        self.backups_label = QLabel()
        self.backups = QComboBox()
        self.restore_button = QPushButton()
        self.restore_button.clicked.connect(self._restore)
        layout.addSpacing(12)
        layout.addWidget(self.backups_label)
        layout.addWidget(self.backups)
        layout.addWidget(self.restore_button)

        self.status = QLabel()
        self.status.setObjectName("muted")
        self.status.setWordWrap(True)
        self.close_button = QPushButton()
        self.close_button.clicked.connect(self.accept)
        layout.addWidget(self.status)
        layout.addWidget(self.close_button)

        self._set_game_root(initial_game_root)
        self.retranslate()
        self._refresh_backups()

    def retranslate(self) -> None:
        self.setWindowTitle(tr("Local VPK mods"))
        self.title.setText(tr("Local VPK mods"))
        self.warning.setText(
            tr(
                "Choose a VPK you downloaded yourself and explicitly select the game VPK to "
                "replace. Skin Cat does not download or redistribute mods. The game file is "
                "backed up outside Dota 2 before replacement. Game rules and VAC compatibility "
                "are not confirmed."
            )
        )
        self.game_root_label.setText(tr("Dota 2 folder"))
        self.browse_game_root_button.setText(tr("Choose Dota 2 folder…"))
        self.source_label.setText(tr("Downloaded mod VPK"))
        self.browse_source_button.setText(tr("Choose mod VPK…"))
        self.target_label.setText(tr("Game VPK to replace"))
        self.browse_target_button.setText(tr("Choose target VPK…"))
        self.apply_button.setText(tr("Back up and replace selected VPK"))
        self.backups_label.setText(tr("Available VPK backups"))
        self.restore_button.setText(tr("Restore selected backup"))
        self.close_button.setText(tr("Close"))

    def _set_game_root(self, path: Path | None) -> None:
        self._game_root = path
        self.game_root_path.setText(str(path) if path is not None else "")
        self.target_path.clear()
        self._refresh_backups()

    def _choose_game_root(self) -> None:
        current = str(self._game_root) if self._game_root is not None else str(Path.home())
        selected = QFileDialog.getExistingDirectory(self, tr("Choose Dota 2 folder"), current)
        if selected:
            self._set_game_root(Path(selected))

    def _choose_source(self) -> None:
        selected, _ = QFileDialog.getOpenFileName(
            self,
            tr("Choose downloaded mod VPK"),
            str(Path.home()),
            tr("VPK files (*.vpk)"),
        )
        if selected:
            self.source_path.setText(selected)

    def _choose_target(self) -> None:
        if self._game_root is None:
            QMessageBox.warning(
                self, tr("Dota 2 folder required"), tr("Choose Dota 2 folder first.")
            )
            return
        selected, _ = QFileDialog.getOpenFileName(
            self,
            tr("Choose game VPK to replace"),
            str(self._game_root),
            tr("VPK files (*.vpk)"),
        )
        if selected:
            self.target_path.setText(selected)

    def _service(self) -> VpkModService:
        if self._game_root is None:
            raise VpkModError("Choose Dota 2 folder first.")
        return VpkModService(self._game_root, self._backup_root)

    def _apply(self) -> None:
        if self._is_game_running():
            QMessageBox.warning(
                self, tr("Close Dota 2 first"), tr("Close Dota 2 before replacing game files.")
            )
            return
        if not self.source_path.text() or not self.target_path.text():
            QMessageBox.warning(
                self, tr("VPK files required"), tr("Choose both the downloaded mod and target VPK.")
            )
            return
        source = Path(self.source_path.text())
        target = Path(self.target_path.text())
        confirmation = QMessageBox.question(
            self,
            tr("Confirm VPK replacement"),
            tr(
                "Replace {target} with {source}? A backup will be created outside the game "
                "folder. This may affect game integrity and is not confirmed as safe for online "
                "play or VAC."
            ).format(target=target, source=source.name),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        service = self._service()
        self._start_operation(lambda: service.apply(source, target), "apply")

    def _restore(self) -> None:
        if self._is_game_running():
            QMessageBox.warning(
                self, tr("Close Dota 2 first"), tr("Close Dota 2 before restoring game files.")
            )
            return
        identifier = self.backups.currentData()
        if not isinstance(identifier, str):
            return
        confirmation = QMessageBox.question(
            self,
            tr("Confirm VPK restore"),
            tr("Restore the original game VPK for {path}?").format(
                path=self.backups.currentText()
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.Cancel,
            QMessageBox.StandardButton.Cancel,
        )
        if confirmation != QMessageBox.StandardButton.Yes:
            return
        service = self._service()
        self._start_operation(lambda: service.restore(identifier), "restore")

    def _start_operation(
        self,
        operation: Callable[[], VpkBackup],
        kind: str,
    ) -> None:
        if self._operation_thread is not None:
            return
        thread = QThread(self)
        worker = _VpkOperationWorker(operation)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.completed.connect(thread.quit)
        worker.failed.connect(thread.quit)
        worker.completed.connect(self._operation_succeeded)
        worker.failed.connect(self._operation_failed)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(self._operation_finished)
        thread.finished.connect(thread.deleteLater)
        self._operation_thread = thread
        self._operation_worker = worker
        self._operation_kind = kind
        self._set_busy(True)
        self.status.setText(
            tr("Applying VPK and creating a backup…")
            if kind == "apply"
            else tr("Restoring the original VPK…")
        )
        thread.start()

    @Slot(object)
    def _operation_succeeded(self, backup: VpkBackup) -> None:
        if self._operation_kind == "apply":
            self.status.setText(
                tr("VPK replaced. Original backup: {path}").format(path=backup.backup_file)
            )
            self.source_path.clear()
        else:
            self.status.setText(tr("Original VPK restored: {path}").format(path=backup.target))
        self._refresh_backups()

    @Slot(str)
    def _operation_failed(self, message: str) -> None:
        title = tr("VPK replacement failed") if self._operation_kind == "apply" else tr(
            "VPK restore failed"
        )
        QMessageBox.critical(self, title, message)

    def _set_busy(self, busy: bool) -> None:
        for button in (
            self.browse_game_root_button,
            self.browse_source_button,
            self.browse_target_button,
            self.apply_button,
            self.restore_button,
            self.close_button,
        ):
            button.setEnabled(not busy)

    @Slot()
    def _operation_finished(self) -> None:
        self._operation_thread = None
        self._operation_worker = None
        self._operation_kind = None
        self._set_busy(False)

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._operation_thread is not None:
            event.ignore()
            return
        super().closeEvent(event)

    def _refresh_backups(self) -> None:
        self.backups.clear()
        self.restore_button.setEnabled(False)
        if self._game_root is None or not self._game_root.is_dir():
            return
        try:
            backups = self._service().list_backups()
        except (VpkModError, OSError) as exc:
            self.status.setText(str(exc))
            return
        for backup in backups:
            if backup.status not in {"pending", "applied"}:
                continue
            try:
                relative_target = backup.target.relative_to(self._game_root.resolve())
            except ValueError:
                continue
            self.backups.addItem(
                f"{relative_target} — {backup.source_name}",
                backup.identifier,
            )
        self.restore_button.setEnabled(self.backups.count() > 0)
