"""Minimal waiting window and settings dialog."""

from __future__ import annotations

import sqlite3
from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import (
    QAbstractAnimation,
    QEasingCurve,
    QEvent,
    QRectF,
    Qt,
    QTimer,
    QVariantAnimation,
)
from PySide6.QtGui import (
    QColor,
    QCursor,
    QIcon,
    QKeySequence,
    QPainter,
    QPainterPath,
    QPaintEvent,
    QPixmap,
)
from PySide6.QtSvg import QSvgRenderer
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QKeySequenceEdit,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QSystemTrayIcon,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from skin_studio.config import AppPaths, Settings, is_valid_hotkey, save_settings, system_language
from skin_studio.i18n.manager import LanguageManager
from skin_studio.services.game_presence import GamePresenceService
from skin_studio.services.steam_detection import discover_steam
from skin_studio.storage.repositories.cosmetics import CosmeticRepository
from skin_studio.ui.widgets.companion_overlay import CompanionOverlayWindow
from skin_studio.ui.widgets.database_backup_dialog import DatabaseBackupDialog
from skin_studio.ui.widgets.player_stats_dialog import PlayerStatsDialog


def tr(source: str) -> str:
    return LanguageManager.text(source)


class WaitingCatWidget(QWidget):
    """Vector cat mark that blinks and lifts both paws while waiting."""

    def __init__(self) -> None:
        super().__init__()
        self.setObjectName("waitingLogo")
        self.setFixedSize(196, 196)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        assets = Path(__file__).parent
        self._open_eyes = QSvgRenderer(str(assets / "skin_cat_logo.svg"))
        self._closed_eyes = QSvgRenderer(str(assets / "skin_cat_logo_blink.svg"))
        self._happy_face = QSvgRenderer(str(assets / "skin_cat_logo_happy.svg"))
        self._raised_paws = QSvgRenderer(str(assets / "cat_paw_white.svg"))
        self._eyes_are_closed = False
        self._gesture_progress = 0.0
        self._joy_progress = 0.0

        self._blink_timer = QTimer(self)
        self._blink_timer.setInterval(3600)
        self._blink_timer.timeout.connect(self._blink)
        self._open_eyes_timer = QTimer(self)
        self._open_eyes_timer.setSingleShot(True)
        self._open_eyes_timer.setInterval(150)
        self._open_eyes_timer.timeout.connect(self._open_eyes_now)
        self._gesture_timer = QTimer(self)
        self._gesture_timer.setInterval(5000)
        self._gesture_timer.timeout.connect(self._raise_both_paws)
        self._first_gesture_timer = QTimer(self)
        self._first_gesture_timer.setSingleShot(True)
        self._first_gesture_timer.setInterval(900)
        self._first_gesture_timer.timeout.connect(self._raise_both_paws)

        self._gesture_animation = QVariantAnimation(self)
        self._gesture_animation.setDuration(1900)
        self._gesture_animation.setStartValue(0.0)
        self._gesture_animation.setKeyValueAt(0.16, 0.9)
        self._gesture_animation.setKeyValueAt(0.32, 1.0)
        self._gesture_animation.setKeyValueAt(0.62, 1.0)
        self._gesture_animation.setKeyValueAt(0.82, 0.72)
        self._gesture_animation.setEndValue(0.0)
        self._gesture_animation.setEasingCurve(QEasingCurve.Type.InOutSine)
        self._gesture_animation.valueChanged.connect(self._set_gesture_progress)
        self._joy_animation = QVariantAnimation(self)
        self._joy_animation.setDuration(520)
        self._joy_animation.setStartValue(0.0)
        self._joy_animation.setEndValue(1.0)
        self._joy_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._joy_animation.valueChanged.connect(self._set_joy_progress)

    def start_waiting_animation(self) -> None:
        self._blink_timer.start()
        if self._gesture_animation.state() != QAbstractAnimation.State.Running:
            self._first_gesture_timer.start()
        self._gesture_timer.start()

    def stop_waiting_animation(self) -> None:
        self._blink_timer.stop()
        self._open_eyes_timer.stop()
        self._first_gesture_timer.stop()
        self._gesture_timer.stop()
        self._gesture_animation.stop()
        self._eyes_are_closed = False
        self._set_gesture_progress(0.0)

    def _blink(self) -> None:
        self._eyes_are_closed = True
        self.update()
        self._open_eyes_timer.start()

    def _open_eyes_now(self) -> None:
        self._eyes_are_closed = False
        self.update()

    def _raise_both_paws(self) -> None:
        if self._gesture_animation.state() != QAbstractAnimation.State.Running:
            self._gesture_animation.start()

    def _set_gesture_progress(self, value: float) -> None:
        self._gesture_progress = float(value)
        self.update()

    def set_game_active(self, active: bool) -> None:
        self._joy_animation.stop()
        self._joy_animation.setStartValue(self._joy_progress)
        self._joy_animation.setEndValue(1.0 if active else 0.0)
        self._joy_animation.setEasingCurve(
            QEasingCurve.Type.OutCubic if active else QEasingCurve.Type.InOutCubic
        )
        self._joy_animation.start()

    def _set_joy_progress(self, value: float) -> None:
        self._joy_progress = float(value)
        self.update()

    def paintEvent(self, event: QPaintEvent) -> None:
        del event
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        if self._joy_progress <= 0.001:
            (self._closed_eyes if self._eyes_are_closed else self._open_eyes).render(painter)
        else:
            painter.save()
            painter.setOpacity(1.0 - self._joy_progress)
            self._open_eyes.render(painter)
            painter.setOpacity(self._joy_progress)
            self._happy_face.render(painter)
            painter.restore()
        if self._gesture_progress > 0.001:
            painter.save()
            painter.setOpacity(min(1.0, self._gesture_progress * 3.0))
            center_x = self.width() * 0.5
            center_y = self.height() * 0.85
            scale = 1.0 + self._gesture_progress * 0.12
            painter.translate(0, (1.0 - self._gesture_progress) * 22)
            painter.translate(center_x, center_y)
            painter.scale(scale, scale)
            painter.translate(-center_x, -center_y)
            paw_width = 46.0
            paw_height = 40.0
            paw_y = 129.0
            self._raised_paws.render(painter, QRectF(45.0, paw_y, paw_width, paw_height))
            self._raised_paws.render(painter, QRectF(105.0, paw_y, paw_width, paw_height))
            painter.restore()


class MainWindow(QMainWindow):
    def __init__(
        self,
        *,
        paths: AppPaths,
        settings: Settings,
        connection: sqlite3.Connection,
        language_manager: LanguageManager,
        game_presence_service: GamePresenceService | None = None,
        global_shortcut_service: object | None = None,
    ) -> None:
        super().__init__()
        self._paths = paths
        self._connection = connection
        self._settings = settings
        self._language_manager = language_manager
        self._game_presence_service = game_presence_service or GamePresenceService()
        self._global_shortcut_service = global_shortcut_service
        self._shortcut_status_source = "Global shortcut is not available in this session."
        self._shortcut_status = tr(self._shortcut_status_source)
        if self._global_shortcut_service is not None:
            self._shortcut_status_source = "Registering the global overlay shortcut."
            self._shortcut_status = tr(self._shortcut_status_source)
            self._global_shortcut_service.activated.connect(self._toggle_overlay_hotkey)
            self._global_shortcut_service.status_changed.connect(self._shortcut_status_changed)
        self._cosmetic_repository = CosmeticRepository(connection)
        self._dota_detected = False
        self._overlay_enabled = True
        self._overlay_auto_shown = False
        self._overlay_window: CompanionOverlayWindow | None = None
        self._tray_icon: QSystemTrayIcon | None = None
        self._tray_open_action = None
        self._tray_exit_action = None
        self._settings_page: SettingsPage | None = None
        self._settings_dialog: QDialog | None = None
        self._player_stats_dialog: PlayerStatsDialog | None = None

        root = QWidget()
        root.setObjectName("waitingRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(28, 22, 28, 24)
        header = QHBoxLayout()
        header.addStretch(1)
        self.settings_button = QToolButton()
        self.settings_button.setObjectName("settingsButton")
        self.settings_button.clicked.connect(self._open_settings)
        header.addWidget(self.settings_button)
        layout.addLayout(header)

        layout.addStretch(1)
        self.logo = WaitingCatWidget()
        layout.addWidget(self.logo, 0, Qt.AlignmentFlag.AlignHCenter)

        self.brand = QLabel("Skin Cat")
        self.brand.setObjectName("waitingBrand")
        self.brand.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addSpacing(15)
        layout.addWidget(self.brand)
        self.status = QLabel()
        self.status.setObjectName("waitingStatus")
        self.status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status)
        self.status_detail = QLabel()
        self.status_detail.setObjectName("waitingDetail")
        self.status_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_detail)
        self.player_stats_button = QPushButton()
        self.player_stats_button.clicked.connect(self._open_player_stats)
        layout.addWidget(self.player_stats_button, 0, Qt.AlignmentFlag.AlignHCenter)
        layout.addStretch(1)
        self.setCentralWidget(root)
        self.setMinimumSize(720, 520)
        self._waiting_phase = 0
        self._waiting_status_timer = QTimer(self)
        self._waiting_status_timer.setInterval(520)
        self._waiting_status_timer.timeout.connect(self._animate_waiting_status)
        self.retranslate()
        self._setup_tray_icon()

        self._presence_timer = QTimer(self)
        self._presence_timer.setInterval(3000)
        self._presence_timer.timeout.connect(self._poll_game_presence)
        self._poll_game_presence()
        self._presence_timer.start()

    def _setup_tray_icon(self) -> None:
        if not QSystemTrayIcon.isSystemTrayAvailable():
            return
        self._tray_icon = QSystemTrayIcon(self._make_tray_icon(), self)
        self._tray_icon.setToolTip(tr("Skin Cat is running in the background"))
        menu = QMenu(self)
        self._tray_open_action = menu.addAction(tr("Open Skin Cat"))
        self._tray_open_action.triggered.connect(self._restore_from_tray)
        menu.addSeparator()
        self._tray_exit_action = menu.addAction(tr("Quit Skin Cat"))
        self._tray_exit_action.triggered.connect(self._exit_from_tray)
        self._tray_icon.setContextMenu(menu)
        self._tray_icon.activated.connect(self._tray_activated)
        self._tray_icon.show()

    def _animate_waiting_status(self) -> None:
        self._waiting_phase = (self._waiting_phase + 1) % 4
        self.status.setText(f"{tr('Waiting for Dota 2 to start')}{'.' * self._waiting_phase}")

    def _start_waiting_animation(self) -> None:
        if not self._waiting_status_timer.isActive():
            self._waiting_phase = 0
            self.status.setText(tr("Waiting for Dota 2 to start"))
            self._waiting_status_timer.start()
        self.logo.start_waiting_animation()

    def _stop_waiting_animation(self) -> None:
        self._waiting_status_timer.stop()
        self.logo.stop_waiting_animation()

    @staticmethod
    def _make_tray_icon() -> QIcon:
        pixmap = QPixmap(32, 32)
        pixmap.fill(Qt.GlobalColor.transparent)
        painter = QPainter(pixmap)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        cat = QPainterPath()
        cat.moveTo(4, 13)
        cat.lineTo(7, 3)
        cat.lineTo(15, 9)
        cat.lineTo(17, 9)
        cat.lineTo(25, 3)
        cat.lineTo(28, 13)
        cat.cubicTo(30, 22, 24, 29, 16, 29)
        cat.cubicTo(8, 29, 2, 22, 4, 13)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#d74f98"))
        painter.drawPath(cat)
        painter.setBrush(QColor("#171719"))
        painter.drawEllipse(10, 16, 2, 3)
        painter.drawEllipse(20, 16, 2, 3)
        painter.end()
        return QIcon(pixmap)

    def _open_settings(self) -> None:
        dialog = QDialog(self)
        dialog.setObjectName("settingsDialog")
        page = SettingsPage(
            self._paths,
            self._settings,
            on_language_changed=self._change_language,
            on_settings_changed=self._persist_settings,
            on_configure_shortcut=(
                self._configure_global_shortcut
                if self._global_shortcut_service is not None
                else None
            ),
            on_shortcut_changed=(
                self._change_global_shortcut if self._global_shortcut_service is not None else None
            ),
            on_manage_backup_restore=self._manage_database_backup,
            shortcut_status=self._shortcut_status,
        )
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(dialog.reject)
        buttons.accepted.connect(dialog.accept)
        dialog_layout = QVBoxLayout(dialog)
        dialog_layout.addWidget(page)
        dialog_layout.addWidget(buttons)
        dialog.resize(620, 620)
        self._settings_page = page
        self._settings_dialog = dialog
        self._settings_page.retranslate()
        self._settings_dialog.setWindowTitle(tr("Settings"))
        dialog.exec()
        self._settings_page = None
        self._settings_dialog = None

    def _manage_database_backup(self) -> None:
        dialog = DatabaseBackupDialog(self, self._connection, self._paths.database)
        dialog.setStyleSheet((Path(__file__).parent / "styles.qss").read_text(encoding="utf-8"))
        dialog.exec()
        if self._overlay_window is not None:
            self._overlay_window.catalog_page.refresh_items()
            self._overlay_window.refresh_selection()

    def _persist_settings(self) -> None:
        try:
            save_settings(self._paths.settings, self._settings)
        except (OSError, ValueError):
            return

    def _change_language(self, language: str) -> None:
        self._settings.language = language
        self._persist_settings()
        self._language_manager.set_language(language)
        self.retranslate()
        if self._settings_page is not None:
            self._settings_page.retranslate()
            if self._settings_dialog is not None:
                self._settings_dialog.setWindowTitle(tr("Settings"))

    def _open_overlay(self) -> None:
        if self._overlay_window is None:
            self._overlay_window = CompanionOverlayWindow(
                self._cosmetic_repository, self._settings.hotkey
            )
            self._overlay_window.setStyleSheet(
                (Path(__file__).parent / "styles.qss").read_text(encoding="utf-8")
            )
        self._overlay_window.refresh_selection()
        self._overlay_window.retranslate()
        screen = QApplication.screenAt(QCursor.pos()) or QApplication.primaryScreen()
        self._overlay_window.place_compact(screen)
        self._overlay_window.show()

    def _toggle_overlay_hotkey(self) -> None:
        if not self._overlay_enabled or not self._dota_detected:
            return
        if self._overlay_window is None:
            self._open_overlay()
            self._overlay_auto_shown = True
            self._overlay_window.expand()
            return
        if not self._overlay_window.isVisible():
            self._overlay_window.show()
            self._overlay_auto_shown = True
            if not self._overlay_window.is_expanded:
                self._overlay_window.expand()
            return
        self._overlay_window.toggle()

    def _configure_global_shortcut(self) -> None:
        if self._global_shortcut_service is not None:
            self._global_shortcut_service.configure()

    def _change_global_shortcut(self, shortcut: str) -> None:
        self._settings.hotkey = shortcut
        self._persist_settings()
        if self._global_shortcut_service is not None:
            self._global_shortcut_service.set_shortcut(shortcut)
        if self._overlay_window is not None:
            self._overlay_window.set_shortcut(shortcut)

    def _shortcut_status_changed(self, status: str) -> None:
        self._shortcut_status_source = status
        self._shortcut_status = tr(status)
        if self._settings_page is not None:
            self._settings_page.set_shortcut_status(self._shortcut_status)

    def _poll_game_presence(self) -> None:
        detected = self._game_presence_service.is_dota_running()
        was_detected = self._dota_detected
        if detected and self._player_stats_dialog is not None:
            self._player_stats_dialog.reject()
        if detected != was_detected:
            self.logo.set_game_active(detected)
        self._set_game_status(detected)
        if detected and self._overlay_enabled:
            if self._overlay_window is None or not self._overlay_window.isVisible():
                self._open_overlay()
                self._overlay_auto_shown = True
        elif not detected and was_detected and self._overlay_auto_shown:
            if self._overlay_window is not None:
                if self._overlay_window.is_expanded:
                    self._overlay_window.collapse()
                self._overlay_window.hide()
            self._overlay_auto_shown = False
        self._dota_detected = detected

    def _open_player_stats(self) -> None:
        if self._dota_detected or self._player_stats_dialog is not None:
            return
        dialog = PlayerStatsDialog(self)
        dialog.setStyleSheet((Path(__file__).parent / "styles.qss").read_text(encoding="utf-8"))
        self._player_stats_dialog = dialog
        try:
            dialog.exec()
        finally:
            self._player_stats_dialog = None

    def _set_game_status(self, detected: bool) -> None:
        self.player_stats_button.setText(tr("Public player history"))
        self.player_stats_button.setEnabled(not detected)
        if detected:
            self.status.setText(tr("Dota 2 detected"))
            self.status_detail.setText(tr("The Skin Cat overlay is ready on your desktop."))
            self._stop_waiting_animation()
        else:
            self.status.setText(f"{tr('Waiting for Dota 2 to start')}{'.' * self._waiting_phase}")
            self.status_detail.setText(tr("The overlay will appear when Dota 2 starts."))
            if self._overlay_enabled:
                self._start_waiting_animation()
            else:
                self._stop_waiting_animation()

    def _restore_from_tray(self) -> None:
        self._overlay_enabled = True
        self.showNormal()
        self.raise_()
        self.activateWindow()
        self._poll_game_presence()

    def _tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (
            QSystemTrayIcon.ActivationReason.Trigger,
            QSystemTrayIcon.ActivationReason.DoubleClick,
        ):
            self._restore_from_tray()

    def _exit_from_tray(self) -> None:
        self._overlay_enabled = False
        self._presence_timer.stop()
        if self._overlay_window is not None:
            self._overlay_window.close()
        if self._tray_icon is not None:
            self._tray_icon.hide()
            self._tray_icon = None
        self.close()

    def closeEvent(self, event: QEvent) -> None:
        if self._tray_icon is not None:
            self._overlay_enabled = False
            self._stop_waiting_animation()
            if self._overlay_window is not None:
                if self._overlay_window.is_expanded:
                    self._overlay_window.collapse()
                self._overlay_window.hide()
            self._overlay_auto_shown = False
            self.hide()
            event.ignore()
            return
        self._presence_timer.stop()
        self._stop_waiting_animation()
        if self._overlay_window is not None:
            self._overlay_window.close()
        event.accept()

    def retranslate(self) -> None:
        self.setWindowTitle(tr("Skin Cat"))
        self.settings_button.setText("⚙")
        self.settings_button.setAccessibleName(tr("Settings"))
        self.settings_button.setToolTip(tr("Settings"))
        if self._tray_icon is not None:
            self._tray_icon.setToolTip(tr("Skin Cat is running in the background"))
        if self._tray_open_action is not None:
            self._tray_open_action.setText(tr("Open Skin Cat"))
        if self._tray_exit_action is not None:
            self._tray_exit_action.setText(tr("Quit Skin Cat"))
        self.player_stats_button.setText(tr("Public player history"))
        self._set_game_status(self._dota_detected)
        if self._overlay_window is not None:
            self._overlay_window.retranslate()
        if self._settings_page is not None:
            self._settings_page.set_shortcut_status(tr(self._shortcut_status_source))


class SettingsPage(QWidget):
    def __init__(
        self,
        paths: AppPaths,
        settings: Settings,
        *,
        on_language_changed: Callable[[str], None],
        on_settings_changed: Callable[[], None],
        on_configure_shortcut: Callable[[], None] | None = None,
        on_shortcut_changed: Callable[[str], None] | None = None,
        on_manage_backup_restore: Callable[[], None] | None = None,
        shortcut_status: str = "",
    ) -> None:
        super().__init__()
        self._paths = paths
        self._settings = settings
        self._on_language_changed = on_language_changed
        self._on_settings_changed = on_settings_changed
        self._on_configure_shortcut = on_configure_shortcut
        self._on_shortcut_changed = on_shortcut_changed
        self._on_manage_backup_restore = on_manage_backup_restore
        layout = QVBoxLayout(self)
        layout.setContentsMargins(42, 38, 42, 32)
        self.title = QLabel()
        self.title.setObjectName("pageTitle")
        self.language_label = QLabel()
        self.language = QComboBox()
        self.language.addItem("English", "en")
        self.language.addItem("Русский", "ru")
        self.language.currentIndexChanged.connect(self._language_selected)
        self.language_note = QLabel()
        self.language_note.setObjectName("muted")
        self.steam_label = QLabel()
        self.steam_path = QLineEdit(settings.steam_path or "")
        self.steam_path.editingFinished.connect(self._steam_path_changed)
        self.detect_button = QPushButton()
        self.detect_button.clicked.connect(self._detect_steam)
        self.steam_result = QLabel()
        self.steam_result.setObjectName("notice")
        self.steam_result.setWordWrap(True)
        self.data_location = QLabel()
        self.data_location.setObjectName("muted")
        self.shortcut_label = QLabel()
        self.shortcut_label.setObjectName("sectionTitle")
        self.shortcut_status = QLabel(shortcut_status)
        self.shortcut_status.setObjectName("muted")
        self.shortcut_status.setWordWrap(True)
        self.shortcut_edit = QKeySequenceEdit(QKeySequence(settings.hotkey))
        self.shortcut_edit.setMaximumSequenceLength(1)
        self.shortcut_edit.setAccessibleName(tr("Global overlay shortcut"))
        self.shortcut_apply_button = QPushButton()
        self.shortcut_apply_button.clicked.connect(self._apply_shortcut)
        self.shortcut_button = QPushButton()
        self.shortcut_button.clicked.connect(self._configure_shortcut)
        self.backup_button = QPushButton()
        self.backup_button.clicked.connect(self._manage_backup_restore)
        layout.addWidget(self.title)
        layout.addSpacing(20)
        layout.addWidget(self.language_label)
        layout.addWidget(self.language)
        layout.addWidget(self.language_note)
        layout.addSpacing(20)
        layout.addWidget(self.steam_label)
        layout.addWidget(self.steam_path)
        layout.addWidget(self.detect_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.steam_result)
        layout.addSpacing(20)
        layout.addWidget(self.shortcut_label)
        layout.addWidget(self.shortcut_edit)
        layout.addWidget(self.shortcut_apply_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.shortcut_status)
        layout.addWidget(self.shortcut_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addSpacing(12)
        layout.addWidget(self.data_location)
        layout.addWidget(self.backup_button, 0, Qt.AlignmentFlag.AlignLeft)
        layout.addStretch(1)
        self.retranslate()
        self._set_language_selection(settings.language or system_language())

    def _set_language_selection(self, language: str) -> None:
        index = self.language.findData(language)
        if index >= 0:
            self.language.blockSignals(True)
            self.language.setCurrentIndex(index)
            self.language.blockSignals(False)

    def _configure_shortcut(self) -> None:
        if self._on_configure_shortcut is not None:
            self._on_configure_shortcut()

    def _manage_backup_restore(self) -> None:
        if self._on_manage_backup_restore is not None:
            self._on_manage_backup_restore()

    def _apply_shortcut(self) -> None:
        shortcut = self.shortcut_edit.keySequence().toString(
            QKeySequence.SequenceFormat.PortableText
        )
        if not is_valid_hotkey(shortcut):
            self.shortcut_status.setText(tr("Choose a modifier and a single key."))
            return
        self._settings.hotkey = shortcut
        self._on_settings_changed()
        if self._on_shortcut_changed is not None:
            self._on_shortcut_changed(shortcut)
        else:
            self.shortcut_status.setText(tr("Shortcut saved. Restart Skin Cat to apply it."))

    def set_shortcut_status(self, status: str) -> None:
        self.shortcut_status.setText(status)

    def _language_selected(self, index: int) -> None:
        language = self.language.itemData(index)
        if language:
            self._on_language_changed(language)

    def _steam_path_changed(self) -> None:
        value = self.steam_path.text().strip()
        self._settings.steam_path = value or None
        self._on_settings_changed()

    def _detect_steam(self) -> None:
        self._steam_path_changed()
        installs = discover_steam(self._settings.steam_path)
        if not installs:
            self.steam_result.setText(tr("Steam or Dota 2 was not found."))
            return
        lines = [tr("Found {count} installation(s).").replace("{count}", str(len(installs)))]
        for install in installs:
            lines.append(f"{install.game_path}  ·  {install.compatibility}")
        self.steam_result.setText("\n".join(lines))

    def retranslate(self) -> None:
        self.title.setText(tr("Settings"))
        self.language_label.setText(tr("Language"))
        self.language_note.setText(tr("The language changes immediately and is saved locally."))
        self.steam_label.setText(tr("Steam installation path (optional override)"))
        self.steam_path.setPlaceholderText(tr("Leave empty to search common locations"))
        self.detect_button.setText(tr("Find Steam installation"))
        self.shortcut_label.setText(tr("Global overlay shortcut"))
        self.shortcut_apply_button.setText(tr("Apply shortcut"))
        self.shortcut_button.setText(tr("Configure shortcut"))
        self.backup_button.setText(tr("Back up or restore application data"))
        self.shortcut_edit.setToolTip(tr("Choose a modifier and a single key."))
        shortcut_available = (
            self._on_configure_shortcut is not None or self._on_shortcut_changed is not None
        )
        self.shortcut_label.setVisible(shortcut_available)
        self.shortcut_edit.setVisible(shortcut_available)
        self.shortcut_apply_button.setVisible(shortcut_available)
        self.shortcut_status.setVisible(shortcut_available)
        self.shortcut_button.setVisible(self._on_configure_shortcut is not None)
        self.data_location.setText(
            tr("Application data is stored here: {path}").replace(
                "{path}", str(self._paths.data_dir)
            )
        )
        self.language.setItemText(self.language.findData("en"), tr("English"))
        self.language.setItemText(self.language.findData("ru"), tr("Russian"))
        self._set_language_selection(self._settings.language or system_language())
