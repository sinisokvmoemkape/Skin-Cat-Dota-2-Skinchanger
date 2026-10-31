"""Application startup and dependency wiring."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication
from PySide6.QtWidgets import QApplication

from skin_studio import __version__
from skin_studio.config import Settings, app_paths, load_settings, system_language
from skin_studio.i18n.manager import LanguageManager
from skin_studio.logging_setup import configure_logging
from skin_studio.storage.database import connect_database
from skin_studio.ui.main_window import MainWindow


def _arguments(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="skin-cat")
    parser.add_argument("--version", action="version", version=f"Skin Cat {__version__}")
    parser.add_argument(
        "--smoke", action="store_true", help="create the main window and exit without a GUI loop"
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    arguments = _arguments(argv)
    paths = app_paths()
    paths.data_dir.mkdir(parents=True, exist_ok=True)
    paths.config_dir.mkdir(parents=True, exist_ok=True)
    logger = configure_logging(paths.logs_dir)
    try:
        settings = load_settings(paths.settings)
    except ValueError:
        logger.exception("Settings could not be loaded; using defaults")
        settings = Settings()

    app = QApplication.instance() or QApplication(sys.argv[:1])
    QCoreApplication.setOrganizationName("Skin Cat")
    QCoreApplication.setApplicationName("Skin Cat")
    app.setStyle("Fusion")
    language = settings.language or system_language()
    language_manager = LanguageManager(app, language)

    shortcut_service = None
    if sys.platform == "linux" and not arguments.smoke:
        from skin_studio.services.global_shortcut import GlobalShortcutService

        shortcut_service = GlobalShortcutService(settings.hotkey)
        app.aboutToQuit.connect(shortcut_service.stop)
    elif sys.platform == "win32" and not arguments.smoke:
        from skin_studio.services.windows_shortcut import WindowsGlobalShortcutService

        shortcut_service = WindowsGlobalShortcutService(settings.hotkey)
        app.aboutToQuit.connect(shortcut_service.stop)

    connection = connect_database(paths.database)
    app.aboutToQuit.connect(connection.close)
    window = MainWindow(
        paths=paths,
        settings=settings,
        connection=connection,
        language_manager=language_manager,
        global_shortcut_service=shortcut_service,
    )
    style_path = Path(__file__).parent / "ui" / "styles.qss"
    window.setStyleSheet(style_path.read_text(encoding="utf-8"))
    window.show()
    if shortcut_service is not None:
        shortcut_service.start()

    if arguments.smoke:
        app.processEvents()
        window.close()
        connection.close()
        print("GUI startup smoke check passed")
        return 0
    logger.info("Application started")
    return app.exec()
