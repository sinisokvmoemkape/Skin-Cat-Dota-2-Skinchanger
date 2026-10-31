"""Compact OS-managed companion window with local-only tabs."""

from pathlib import Path

from PySide6.QtCore import QEasingCurve, QPropertyAnimation, QSize, Qt
from PySide6.QtGui import QIcon
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from skin_studio.i18n.manager import LanguageManager
from skin_studio.storage.repositories.cosmetics import CosmeticRepository
from skin_studio.ui.pages.cosmetic_catalog_page import CosmeticCatalogPage


def tr(source: str) -> str:
    return LanguageManager.text(source)


class CompanionOverlayWindow(QWidget):
    """A normal topmost desktop window; it never attaches to the game process."""

    COMPACT_SIZE = 44
    PANEL_WIDTH = 760
    PANEL_HEIGHT = 640

    def __init__(self, cosmetics: CosmeticRepository, shortcut: str = "Ctrl+Shift+O") -> None:
        flags = (
            Qt.WindowType.Tool
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.FramelessWindowHint
        )
        super().__init__(None, flags)
        self._cosmetics = cosmetics
        self._expanded = False
        self._anchor_screen = None
        self._shortcut = shortcut
        self.setObjectName("companionOverlay")
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setAttribute(Qt.WidgetAttribute.WA_ShowWithoutActivating, True)
        self.setFixedSize(self.COMPACT_SIZE, self.COMPACT_SIZE)

        self.root_layout = QVBoxLayout(self)
        self.root_layout.setContentsMargins(0, 0, 0, 0)
        self.icon_button = QPushButton()
        self.icon_button.setObjectName("overlayLauncher")
        icon_path = Path(__file__).parent.parent / "skin_cat_launcher.svg"
        self.icon_button.setIcon(QIcon(str(icon_path)))
        self.icon_button.setIconSize(QSize(27, 27))
        self.icon_button.clicked.connect(self.expand)
        self.root_layout.addWidget(self.icon_button)

        self.panel = QFrame()
        self.panel.setObjectName("overlayPanel")
        panel_layout = QVBoxLayout(self.panel)
        panel_layout.setContentsMargins(18, 14, 18, 14)
        panel_layout.setSpacing(10)

        header = QHBoxLayout()
        heading = QVBoxLayout()
        heading.setSpacing(2)
        self.title = QLabel()
        self.title.setObjectName("pageTitle")
        self.subtitle = QLabel()
        self.subtitle.setObjectName("muted")
        heading.addWidget(self.title)
        heading.addWidget(self.subtitle)
        self.collapse_button = QPushButton("×")
        self.collapse_button.setObjectName("overlayCollapseButton")
        self.collapse_button.clicked.connect(self.collapse)
        header.addLayout(heading, 1)
        header.addWidget(self.collapse_button)

        self.tabs = QTabWidget()
        self.stats_page = QWidget()
        stats_layout = QVBoxLayout(self.stats_page)
        stats_layout.setContentsMargins(8, 14, 8, 8)
        stats_layout.setSpacing(12)
        self.stats_title = QLabel()
        self.stats_title.setObjectName("sectionTitle")
        self.stats_card = QFrame()
        self.stats_card.setObjectName("overlayCard")
        stats_card_layout = QVBoxLayout(self.stats_card)
        stats_card_layout.setContentsMargins(18, 18, 18, 18)
        stats_card_layout.setSpacing(10)
        self.stats_message = QLabel()
        self.stats_message.setObjectName("statsEmptyState")
        self.stats_message.setWordWrap(True)
        self.stats_note = QLabel()
        self.stats_note.setObjectName("notice")
        self.stats_note.setWordWrap(True)
        stats_card_layout.addWidget(self.stats_message)
        stats_card_layout.addWidget(self.stats_note)
        stats_layout.addWidget(self.stats_title)
        stats_layout.addWidget(self.stats_card)
        stats_layout.addStretch(1)

        self.cosmetics_page = QWidget()
        cosmetics_layout = QVBoxLayout(self.cosmetics_page)
        cosmetics_layout.setContentsMargins(0, 0, 0, 0)
        cosmetics_layout.setSpacing(8)
        self.catalog_page = CosmeticCatalogPage(cosmetics, compact=True)
        cosmetics_layout.addWidget(self.catalog_page, 1)

        self.hero_page = QWidget()
        hero_layout = QVBoxLayout(self.hero_page)
        hero_layout.setContentsMargins(8, 14, 8, 8)
        hero_layout.setSpacing(12)
        self.hero_title = QLabel()
        self.hero_title.setObjectName("sectionTitle")
        self.hero_message = QLabel()
        self.hero_message.setObjectName("overlayCardText")
        self.hero_message.setWordWrap(True)
        self.hero_card = QFrame()
        self.hero_card.setObjectName("overlayCard")
        hero_card_layout = QVBoxLayout(self.hero_card)
        hero_card_layout.setContentsMargins(18, 18, 18, 18)
        hero_card_layout.addWidget(self.hero_message)
        hero_layout.addWidget(self.hero_title)
        hero_layout.addWidget(self.hero_card)
        hero_layout.addStretch(1)

        self.tabs.addTab(self.stats_page, "")
        self.tabs.addTab(self.cosmetics_page, "")
        self.tabs.addTab(self.hero_page, "")

        self.disclaimer = QLabel()
        self.disclaimer.setObjectName("notice")
        self.disclaimer.setWordWrap(True)
        self.shortcut_hint = QLabel()
        self.shortcut_hint.setObjectName("muted")
        self.shortcut_hint.setAlignment(Qt.AlignmentFlag.AlignRight)
        panel_layout.addLayout(header)
        panel_layout.addWidget(self.tabs, 1)
        panel_layout.addWidget(self.disclaimer)
        panel_layout.addWidget(self.shortcut_hint)
        self.root_layout.addWidget(self.panel)
        self.panel.hide()

        self._panel_opacity = QGraphicsOpacityEffect(self.panel)
        self._panel_opacity.setOpacity(1.0)
        self.panel.setGraphicsEffect(self._panel_opacity)
        self._panel_animation = QPropertyAnimation(self._panel_opacity, b"opacity", self)
        self._panel_animation.setDuration(190)
        self._panel_animation.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._panel_animation.finished.connect(self._finish_panel_transition)

        self.tabs.currentChanged.connect(self._tab_changed)
        self.retranslate()
        self.refresh_selection()

    def refresh_selection(self) -> None:
        self.catalog_page.refresh_selection_items()

    def _tab_changed(self, index: int) -> None:
        if index == 1:
            self.catalog_page.refresh_selection_items()
            self.catalog_page.refresh_items()

    def expand(self) -> None:
        if self._expanded:
            return
        self._anchor_screen = QApplication.screenAt(self.frameGeometry().center())
        if self._anchor_screen is None:
            self._anchor_screen = QApplication.primaryScreen()
        self._expanded = True
        self._panel_animation.stop()
        self._panel_opacity.setOpacity(0.0)
        self.icon_button.hide()
        self.panel.show()
        self.setFixedSize(self.PANEL_WIDTH, self.PANEL_HEIGHT)
        if self._anchor_screen is not None:
            bounds = self._anchor_screen.geometry()
            width = min(self.PANEL_WIDTH, bounds.width())
            height = min(self.PANEL_HEIGHT, bounds.height())
            self.setFixedSize(width, height)
            self.move(
                bounds.left() + (bounds.width() - width) // 2,
                bounds.top() + (bounds.height() - height) // 2,
            )
        self._panel_animation.setStartValue(0.0)
        self._panel_animation.setEndValue(1.0)
        self._panel_animation.start()
        self.raise_()
        self.activateWindow()

    def collapse(self) -> None:
        if not self._expanded:
            return
        self._expanded = False
        self._panel_animation.stop()
        self._panel_animation.setStartValue(self._panel_opacity.opacity())
        self._panel_animation.setEndValue(0.0)
        self._panel_animation.start()

    def _finish_panel_transition(self) -> None:
        if self._expanded:
            self._panel_opacity.setOpacity(1.0)
            return
        self.panel.hide()
        self.icon_button.show()
        self._panel_opacity.setOpacity(1.0)
        self.setFixedSize(self.COMPACT_SIZE, self.COMPACT_SIZE)
        self.place_compact(self._anchor_screen)
        self.raise_()

    def place_compact(self, screen=None) -> None:
        """Place the launcher near the upper-left area, inset from screen edges."""
        target_screen = screen or QApplication.primaryScreen()
        if target_screen is None or self._expanded:
            return
        self._anchor_screen = target_screen
        bounds = target_screen.availableGeometry()
        self.move(bounds.left() + 58, bounds.top() + 54)

    def toggle(self) -> None:
        if self._expanded:
            self.collapse()
        else:
            self.expand()

    @property
    def is_expanded(self) -> bool:
        return self._expanded

    def set_shortcut(self, shortcut: str) -> None:
        self._shortcut = shortcut
        self.retranslate()

    def retranslate(self) -> None:
        self.setWindowTitle(tr("Skin Cat overlay"))
        self.icon_button.setToolTip(tr("Open companion overlay"))
        self.icon_button.setAccessibleName(tr("Open companion overlay"))
        self.title.setText(tr("Skin Cat"))
        self.subtitle.setText(tr("Desktop companion for Dota 2"))
        self.collapse_button.setToolTip(tr("Collapse overlay"))
        self.stats_title.setText(tr("Public player history"))
        self.stats_message.setText(
            tr("Public player history is available from the waiting screen while Dota 2 is closed.")
        )
        self.stats_note.setText(
            tr(
                "This overlay does not show player data. It does not access the current match "
                "roster or live game state."
            )
        )
        self.tabs.setTabText(0, tr("History"))
        self.tabs.setTabText(1, tr("Cosmetics"))
        self.tabs.setTabText(2, tr("Hero tier"))
        self.hero_title.setText(tr("Hero tier preview"))
        self.hero_message.setText(
            tr(
                "Hero tier data is not connected. This is a local preview only; it does not change "
                "account progress or Dota 2."
            )
        )
        self.disclaimer.setText(
            tr(
                "This is a separate desktop window. It does not attach to Dota 2 or read game "
                "memory."
            )
        )
        self.shortcut_hint.setText(
            tr("Toggle overlay: {shortcut}").replace("{shortcut}", self._shortcut)
        )
        self.catalog_page.retranslate()
