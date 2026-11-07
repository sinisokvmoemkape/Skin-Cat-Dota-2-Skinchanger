from PySide6.QtCore import QTranslator

from skin_studio.i18n.manager import LanguageManager


def test_both_translation_catalogs_load(qapp) -> None:
    for language in ("en", "ru"):
        translator = QTranslator()
        assert translator.load(str(LanguageManager.catalog_path(language)))
        assert translator.translate("App", "Overview")
        assert translator.translate(
            "App", "Waiting for Dota 2. Detection checks the process name only."
        )
        assert translator.translate("App", "Dota 2 detected. Showing the desktop overlay.")
        assert translator.translate("App", "Open Skin Cat")
        assert translator.translate("App", "Quit Skin Cat")
        assert translator.translate("App", "Active profile")
        assert translator.translate("App", "Browse cosmetics")
        assert translator.translate("App", "Profile contents")
        assert translator.translate("App", "Waiting for Dota 2 to start")
        assert translator.translate("App", "The overlay will appear when Dota 2 starts.")
        assert translator.translate("App", "My selection")
        assert translator.translate("App", "Add to my selection")
        assert translator.translate("App", "Match overview")
        assert translator.translate("App", "Public player history")
        assert translator.translate("App", "Look up public history")
        assert translator.translate("App", "Back up or restore application data")
        assert translator.translate("App", "Apply shortcut")
        assert translator.translate("App", "Toggle overlay: {shortcut}")
        assert translator.translate("App", "Local VPK mods")
        assert translator.translate("App", "Back up and replace selected VPK")
        assert translator.translate("App", "Restore selected backup")
        assert translator.translate("App", "Applying VPK and creating a backup…")
        assert translator.translate("App", "Restoring the original VPK…")
        assert translator.translate("App", "Close Dota 2 before restoring game files.")
        assert translator.translate(
            "App",
            "Replace {target} with {source}? A backup will be created outside the game folder. "
            "This may affect game integrity and is not confirmed as safe for online play or VAC.",
        )


def test_russian_catalog_contains_critical_ui_messages(qapp) -> None:
    translator = QTranslator()
    assert translator.load(str(LanguageManager.catalog_path("ru")))
    qapp.installTranslator(translator)
    try:
        assert qapp.translate("App", "Overview") == "Обзор"
        assert qapp.translate("App", "Delete the selected local profile?") == (
            "Удалить выбранный локальный профиль?"
        )
        assert qapp.translate("App", "Steam or Dota 2 was not found.") == (
            "Steam или Dota 2 не найдены."
        )
        assert (
            qapp.translate("App", "Waiting for Dota 2. Detection checks the process name only.")
            == "Ожидание Dota 2. Проверяется только имя процесса."
        )
        assert qapp.translate("App", "Waiting for Dota 2 to start") == "Ожидание запуска Dota 2"
        assert qapp.translate("App", "My selection") == "Моя подборка"
        assert qapp.translate("App", "Match") == "Матч"
        assert qapp.translate("App", "Apply shortcut") == "Применить клавиши"
        assert qapp.translate("App", "Public player history") == "Публичная история игрока"
        assert qapp.translate(
            "App", "Back up or restore application data"
        ) == "Резервное копирование и восстановление данных"
        assert qapp.translate("App", "Local VPK mods") == "Локальные VPK-моды"
        assert qapp.translate("App", "Back up and replace selected VPK") == (
            "Сохранить копию и заменить VPK"
        )
        assert qapp.translate("App", "Restore selected backup") == (
            "Восстановить выбранную копию"
        )
    finally:
        qapp.removeTranslator(translator)
