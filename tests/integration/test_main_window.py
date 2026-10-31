from pathlib import Path

from PySide6.QtCore import QAbstractAnimation, QObject, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import QDialog

from skin_studio.config import AppPaths, Settings
from skin_studio.i18n.manager import LanguageManager
from skin_studio.storage.database import connect_database
from skin_studio.ui.main_window import MainWindow, SettingsPage
from skin_studio.ui.widgets.player_stats_dialog import PlayerStatsDialog


class FakeShortcutService(QObject):
    activated = Signal()
    status_changed = Signal(str)

    def configure(self) -> None:
        self.status_changed.emit("Shortcut settings opened in the desktop portal.")

    def set_shortcut(self, shortcut: str) -> None:
        self.shortcut = shortcut


def test_minimal_waiting_screen_and_overlay_selection(qapp, tmp_path: Path) -> None:
    class FakeGamePresence:
        running = False

        def is_dota_running(self) -> bool:
            return self.running

    presence = FakeGamePresence()
    paths = AppPaths(
        data_dir=tmp_path / "data",
        config_dir=tmp_path / "config",
        cache_dir=tmp_path / "cache",
    )
    settings = Settings(language="en")
    shortcut_service = FakeShortcutService()
    connection = connect_database(paths.database)
    language_manager = LanguageManager(qapp, "en")
    window = MainWindow(
        paths=paths,
        settings=settings,
        connection=connection,
        language_manager=language_manager,
        game_presence_service=presence,
        global_shortcut_service=shortcut_service,
    )
    try:
        assert window.windowTitle() == "Skin Cat"
        assert window.brand.text() == "Skin Cat"
        assert window.status.text() == "Waiting for Dota 2 to start"
        assert window.status_detail.text() == "The overlay will appear when Dota 2 starts."
        assert window.player_stats_button.text() == "Public player history"
        assert window.player_stats_button.isEnabled()
        assert window.logo._open_eyes.isValid()
        assert window.logo._closed_eyes.isValid()
        assert window.logo._happy_face.isValid()
        assert window.logo._raised_paws.isValid()
        assert window._waiting_status_timer.isActive()
        assert window.logo._blink_timer.isActive()
        assert window.logo._gesture_timer.isActive()
        assert window.logo._first_gesture_timer.isActive()
        assert not hasattr(window, "overlay_button")
        assert not hasattr(window, "_navigation")
        assert not hasattr(window, "profiles_page")
        assert window._overlay_window is None
        window.logo._blink()
        assert window.logo._eyes_are_closed
        window.logo._open_eyes_now()
        assert not window.logo._eyes_are_closed
        window.logo._set_gesture_progress(1.0)
        assert window.logo._gesture_progress == 1.0
        window.logo._set_gesture_progress(0.0)
        window.logo._raise_both_paws()
        assert window.logo._gesture_animation.state() == QAbstractAnimation.State.Running
        window.logo._gesture_animation.stop()

        dialog = PlayerStatsDialog(window)
        dialog.show()
        window._player_stats_dialog = dialog
        presence.running = True
        window._poll_game_presence()
        assert window.status.text() == "Dota 2 detected"
        assert not window.player_stats_button.isEnabled()
        assert dialog.result() == QDialog.DialogCode.Rejected
        window._player_stats_dialog = None
        assert window.status_detail.text() == "The Skin Cat overlay is ready on your desktop."
        assert window._overlay_auto_shown
        assert window._overlay_window.isVisible()
        assert not window._waiting_status_timer.isActive()
        assert not window.logo._blink_timer.isActive()
        assert not window.logo._gesture_timer.isActive()
        assert not window.logo._first_gesture_timer.isActive()
        assert window.logo._joy_animation.state() == QAbstractAnimation.State.Running
        assert window.logo._joy_progress == 0.0
        shortcut_service.activated.emit()
        assert window._overlay_window.is_expanded
        shortcut_service.activated.emit()
        assert not window._overlay_window.is_expanded
        window._overlay_window.icon_button.click()
        assert window._overlay_window.icon_button.icon().isNull() is False
        screen_bounds = window._overlay_window._anchor_screen.geometry()
        assert window._overlay_window.width() == min(
            window._overlay_window.PANEL_WIDTH, screen_bounds.width()
        )
        assert window._overlay_window.frameGeometry().center() == screen_bounds.center()
        assert window._overlay_window.tabs.tabText(0) == "History"
        assert window._overlay_window.tabs.tabText(1) == "Cosmetics"
        assert window._overlay_window.shortcut_hint.text() == "Toggle overlay: Ctrl+Shift+O"

        catalog = window._overlay_window.catalog_page
        assert catalog.items.count() == 11
        catalog.items.setCurrentRow(0)
        catalog._assign_selected()
        assert catalog.selection_items.count() == 1
        assert "Example" in catalog.selection_items.item(0).text()
        assert catalog.selection_summary.text() == "Items in my selection: 1"
        catalog.sections.setCurrentIndex(1)
        assert catalog.sections.tabText(1) == "My selection"
        catalog.selection_items.setCurrentRow(0)
        catalog.remove_selection_item_button.click()
        assert catalog.selection_items.count() == 0
        assert connection.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 0
        assert connection.execute("SELECT COUNT(*) FROM local_selection_items").fetchone()[0] == 0

        window._change_language("ru")
        assert window._settings.language == "ru"
        assert window.status.text() == "Обнаружена Dota 2"
        assert window._overlay_window.tabs.tabText(1) == "Косметика"
        assert catalog.sections.tabText(1) == "Моя подборка"
        assert '"language": "ru"' in paths.settings.read_text(encoding="utf-8")
        presence.running = False
        window._poll_game_presence()
        assert window.status.text() == "Ожидание запуска Dota 2"
        assert not window._overlay_window.isVisible()
        assert window.logo._blink_timer.isActive()
        assert window.logo._gesture_timer.isActive()
        assert window.logo._first_gesture_timer.isActive()
    finally:
        window.close()
        if window._overlay_window is not None:
            window._overlay_window.close()
        connection.close()
        qapp.removeTranslator(language_manager._translator)


def test_close_hides_to_tray_and_explicit_tray_exit_closes(qapp, tmp_path: Path) -> None:
    class FakeTrayIcon:
        hidden = False

        def hide(self) -> None:
            self.hidden = True

    paths = AppPaths(
        data_dir=tmp_path / "data",
        config_dir=tmp_path / "config",
        cache_dir=tmp_path / "cache",
    )
    connection = connect_database(paths.database)
    language_manager = LanguageManager(qapp, "en")
    window = MainWindow(
        paths=paths,
        settings=Settings(language="en"),
        connection=connection,
        language_manager=language_manager,
    )
    tray = FakeTrayIcon()
    window._tray_icon = tray
    try:
        window.show()
        window.close()
        assert not window.isVisible()
        assert window._presence_timer.isActive()
        window._restore_from_tray()
        assert window.isVisible()
        window._exit_from_tray()
        assert tray.hidden
        assert not window._presence_timer.isActive()
        assert not window.isVisible()
    finally:
        window._tray_icon = None
        window.close()
        connection.close()
        qapp.removeTranslator(language_manager._translator)


def test_settings_can_open_desktop_shortcut_configuration(qapp, tmp_path: Path) -> None:
    paths = AppPaths(
        data_dir=tmp_path / "data",
        config_dir=tmp_path / "config",
        cache_dir=tmp_path / "cache",
    )
    calls: list[bool] = []
    backup_calls: list[bool] = []
    page = SettingsPage(
        paths,
        Settings(language="en"),
        on_language_changed=lambda _: None,
        on_settings_changed=lambda: None,
        on_configure_shortcut=lambda: calls.append(True),
        on_shortcut_changed=lambda shortcut: calls.append(shortcut),
        on_manage_backup_restore=lambda: backup_calls.append(True),
        shortcut_status="Global shortcut is ready. Default: Ctrl+Shift+O.",
    )
    assert not page.shortcut_button.isHidden()
    assert not page.shortcut_apply_button.isHidden()
    page.shortcut_edit.setKeySequence(QKeySequence("Ctrl+Alt+K"))
    page.shortcut_apply_button.click()
    assert page._settings.hotkey == "Ctrl+Alt+K"
    assert calls == ["Ctrl+Alt+K"]
    page.shortcut_button.click()
    assert calls == ["Ctrl+Alt+K", True]
    page.backup_button.click()
    assert backup_calls == [True]
    page.set_shortcut_status("Portal permission required.")
    assert page.shortcut_status.text() == "Portal permission required."


def test_overlay_waits_until_skin_cat_is_restored_from_tray(qapp, tmp_path: Path) -> None:
    class FakeGamePresence:
        running = False

        def is_dota_running(self) -> bool:
            return self.running

    class FakeTrayIcon:
        def hide(self) -> None:
            pass

    paths = AppPaths(
        data_dir=tmp_path / "data",
        config_dir=tmp_path / "config",
        cache_dir=tmp_path / "cache",
    )
    connection = connect_database(paths.database)
    language_manager = LanguageManager(qapp, "en")
    presence = FakeGamePresence()
    window = MainWindow(
        paths=paths,
        settings=Settings(language="en"),
        connection=connection,
        language_manager=language_manager,
        game_presence_service=presence,
    )
    window._tray_icon = FakeTrayIcon()
    try:
        window.show()
        window.close()
        assert not window._overlay_enabled
        presence.running = True
        window._poll_game_presence()
        assert window._overlay_window is None
        window._restore_from_tray()
        assert window._overlay_enabled
        assert window._overlay_window is not None
        assert window._overlay_window.isVisible()
    finally:
        window._exit_from_tray()
        window._tray_icon = None
        connection.close()
        qapp.removeTranslator(language_manager._translator)
