"""Runtime Qt translation catalog management."""

from pathlib import Path

from PySide6.QtCore import QCoreApplication, QTranslator


class LanguageManager:
    SUPPORTED = ("en", "ru")

    def __init__(self, application: QCoreApplication, language: str = "en") -> None:
        self._application = application
        self._translator: QTranslator | None = None
        self.language = "en"
        self.set_language(language)

    @staticmethod
    def catalog_path(language: str) -> Path:
        return Path(__file__).parent / "locale" / language / "skin_studio.qm"

    def set_language(self, language: str) -> None:
        if language not in self.SUPPORTED:
            raise ValueError(f"Unsupported language: {language}")
        translator = QTranslator(self._application)
        if not translator.load(str(self.catalog_path(language))):
            raise FileNotFoundError(f"Translation catalog is missing for language {language}")
        if self._translator is not None:
            self._application.removeTranslator(self._translator)
        self._translator = translator
        self._application.installTranslator(translator)
        self.language = language

    @staticmethod
    def text(source: str) -> str:
        return QCoreApplication.translate("App", source)
