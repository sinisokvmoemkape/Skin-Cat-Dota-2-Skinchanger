"""Browsable, clearly labelled sample cosmetic catalog."""

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from skin_studio.domain.models import CosmeticCategory, CosmeticItem
from skin_studio.i18n.manager import LanguageManager
from skin_studio.storage.repositories.cosmetics import CosmeticRepository


def tr(source: str) -> str:
    return LanguageManager.text(source)


CATEGORY_LABELS = {
    CosmeticCategory.HERO_ITEM.value: "Hero cosmetics",
    CosmeticCategory.COURIER.value: "Couriers",
    CosmeticCategory.WARD.value: "Wards",
    CosmeticCategory.WEATHER.value: "Weather effects",
    CosmeticCategory.TERRAIN.value: "Terrains",
    CosmeticCategory.MUSIC.value: "Music packs",
    CosmeticCategory.ANNOUNCER.value: "Announcer packs",
    CosmeticCategory.HUD.value: "HUD themes",
    CosmeticCategory.LOADING_SCREEN.value: "Loading screens",
    CosmeticCategory.TAUNT.value: "Taunts",
    CosmeticCategory.ABILITY_EFFECT.value: "Ability effects",
    CosmeticCategory.OTHER.value: "Other",
}


class CosmeticCatalogPage(QWidget):
    def __init__(
        self,
        cosmetics: CosmeticRepository,
        *,
        compact: bool = False,
    ) -> None:
        super().__init__()
        self._cosmetics = cosmetics
        self._compact = compact
        self._items_by_id: dict[str, CosmeticItem] = {}

        layout = QVBoxLayout(self)
        if compact:
            layout.setContentsMargins(8, 8, 8, 6)
        else:
            layout.setContentsMargins(20, 18, 20, 16)
        self.title = QLabel()
        self.title.setObjectName("pageTitle")
        self.title.setVisible(not compact)
        self.notice = QLabel()
        self.notice.setObjectName("notice")
        self.notice.setWordWrap(True)
        filters = QHBoxLayout()
        self.search = QLineEdit()
        self.search.textChanged.connect(self.refresh_items)
        self.favorites_only = QCheckBox()
        self.favorites_only.toggled.connect(self.refresh_items)
        self.category = QComboBox()
        self.category.currentIndexChanged.connect(self.refresh_items)
        self.hero_filter = QComboBox()
        self.hero_filter.currentIndexChanged.connect(self.refresh_items)
        self.slot_filter = QComboBox()
        self.slot_filter.currentIndexChanged.connect(self.refresh_items)
        filters.addWidget(self.search, 2)
        filters.addWidget(self.category, 1)
        metadata_filters = QHBoxLayout()
        metadata_filters.addWidget(self.hero_filter, 1)
        metadata_filters.addWidget(self.slot_filter, 1)
        self.items = QListWidget()
        self.items.currentItemChanged.connect(self._show_selected_item)
        self.details = QLabel()
        self.details.setObjectName("muted")
        self.details.setWordWrap(True)
        self.favorite_button = QPushButton()
        self.favorite_button.clicked.connect(self._toggle_favorite)
        self.details_row = QHBoxLayout()
        self.details_row.addWidget(self.details, 1)
        self.details_row.addWidget(self.favorite_button)
        self.selection_summary = QLabel()
        self.selection_summary.setObjectName("muted")

        self.sections = QTabWidget()
        self.catalog_section = QWidget()
        catalog_layout = QVBoxLayout(self.catalog_section)
        catalog_layout.setContentsMargins(0, 8, 0, 0)
        catalog_layout.addLayout(filters)
        catalog_layout.addLayout(metadata_filters)
        catalog_layout.addWidget(self.favorites_only)
        catalog_layout.addWidget(self.items, 1)
        catalog_layout.addLayout(self.details_row)
        self.assign_button = QPushButton()
        self.assign_button.setObjectName("primaryButton")
        self.assign_button.clicked.connect(self._assign_selected)
        catalog_layout.addWidget(self.assign_button, 0, Qt.AlignmentFlag.AlignRight)

        self.selection_section = QWidget()
        selection_layout = QVBoxLayout(self.selection_section)
        selection_layout.setContentsMargins(0, 8, 0, 0)
        self.selection_items = QListWidget()
        self.selection_items.currentItemChanged.connect(self._update_remove_button)
        self.remove_selection_item_button = QPushButton()
        self.remove_selection_item_button.clicked.connect(self._remove_selected_item)
        selection_layout.addWidget(self.selection_items, 1)
        selection_layout.addWidget(
            self.remove_selection_item_button, 0, Qt.AlignmentFlag.AlignRight
        )
        self.sections.addTab(self.catalog_section, "")
        self.sections.addTab(self.selection_section, "")
        self.feedback = QLabel()
        self.feedback.setObjectName("muted")
        self.feedback.setWordWrap(True)

        layout.addWidget(self.title)
        layout.addWidget(self.notice)
        layout.addWidget(self.selection_summary)
        layout.addWidget(self.sections, 1)
        layout.addWidget(self.feedback)

        self.retranslate()
        self.refresh_selection_items()
        self.refresh_items()

    def refresh_selection_items(self) -> None:
        self.selection_items.clear()
        items = self._cosmetics.list_local_selection()
        self.selection_summary.setText(
            tr("Items in my selection: {count}").format(count=len(items))
        )
        for item in items:
            category = CATEGORY_LABELS.get(item.category, "Unsupported category")
            name = tr(item.name) if item.is_sample else item.name
            sample = f" · {tr('Sample')}" if item.is_sample else ""
            row = QListWidgetItem(f"{tr(category)} · {name}{sample}")
            row.setData(Qt.ItemDataRole.UserRole, item.identifier)
            self.selection_items.addItem(row)
        self._update_remove_button()

    def _update_remove_button(self, *_args: object) -> None:
        self.remove_selection_item_button.setEnabled(self.selection_items.currentItem() is not None)

    def _remove_selected_item(self) -> None:
        selected = self.selection_items.currentItem()
        if selected is None:
            return
        self._cosmetics.remove_from_local_selection(str(selected.data(Qt.ItemDataRole.UserRole)))
        self.refresh_selection_items()
        self.feedback.setText(tr("Removed from your cosmetic selection."))

    def refresh_items(self) -> None:
        selected_id = (
            self.items.currentItem().data(Qt.ItemDataRole.UserRole)
            if self.items.currentItem()
            else None
        )
        category = self.category.currentData()
        self.items.clear()
        catalog_items = self._cosmetics.list_items(
            query=self.search.text(),
            category=category,
            hero_id=self.hero_filter.currentData(),
            slot=self.slot_filter.currentData(),
            favorites_only=self.favorites_only.isChecked(),
        )
        self._items_by_id = {item.identifier: item for item in catalog_items}
        for item in catalog_items:
            favorite_mark = "★  " if item.is_favorite else ""
            display_name = tr(item.name) if item.is_sample else item.name
            suffix = f"  ·  {tr('Sample')}" if item.is_sample else ""
            row = QListWidgetItem(f"{favorite_mark}{display_name}{suffix}")
            row.setData(Qt.ItemDataRole.UserRole, item.identifier)
            self.items.addItem(row)
            if item.identifier == selected_id:
                self.items.setCurrentItem(row)
        if self.items.count() and self.items.currentItem() is None:
            self.items.setCurrentRow(0)
        if not self.items.count():
            self.details.setText(tr("No catalog entries match these filters."))
            self.favorite_button.setEnabled(False)

    def _show_selected_item(
        self, current: QListWidgetItem | None, _previous: QListWidgetItem | None
    ) -> None:
        if current is None:
            self.details.setText(tr("Select a catalog entry to see its details."))
            self.favorite_button.setEnabled(False)
            return
        item_id = current.data(Qt.ItemDataRole.UserRole)
        item = self._items_by_id.get(item_id)
        if item is None:
            self.details.setText(tr("Catalog entry is unavailable."))
            self.favorite_button.setEnabled(False)
            return
        self.favorite_button.setEnabled(True)
        self.favorite_button.setText(
            tr("Remove from favorites") if item.is_favorite else tr("Add to favorites")
        )
        category_name = CATEGORY_LABELS.get(item.category)
        localized_category = tr(category_name) if category_name else tr("Unsupported category")
        values = {
            "category": localized_category,
            "hero": tr(item.hero_id) if item.hero_id else tr("Not applicable"),
            "slot": tr(item.slot) if item.slot else tr("Not applicable"),
            "source": tr("Sample data") if item.is_sample else item.source,
            "license": tr("Not applicable for sample metadata")
            if item.license_status == "not_applicable"
            else item.license_status,
        }
        full_details = tr(
            "Category: {category}\nHero: {hero}\nSlot: {slot}\nSource: {source}\nLicense: {license}"
        ).format(**values)
        compact_details = tr("Category: {category}\nHero: {hero}\nSlot: {slot}").format(**values)
        self.details.setText(compact_details if self._compact else full_details)
        self.details.setToolTip(full_details)

    def _toggle_favorite(self) -> None:
        current = self.items.currentItem()
        if current is None:
            return
        self._cosmetics.toggle_favorite(str(current.data(Qt.ItemDataRole.UserRole)))
        self.refresh_items()

    def _assign_selected(self) -> None:
        item = self.items.currentItem()
        if item is None:
            self.feedback.setText(tr("Select a catalog entry first."))
            return
        created = self._cosmetics.add_to_local_selection(str(item.data(Qt.ItemDataRole.UserRole)))
        self.feedback.setText(
            tr("Added to your cosmetic selection.")
            if created
            else tr("This entry is already selected.")
        )
        self.refresh_selection_items()

    def retranslate(self) -> None:
        self.title.setText(tr("Cosmetic catalog"))
        if self._compact:
            self.notice.setText(tr("Demo entries only — not real items and not applied to Dota 2."))
        else:
            self.notice.setText(
                tr(
                    "Sample catalog only. These placeholders are not real owned Dota 2 items "
                    "and are not applied to the game."
                )
            )
        self.search.setPlaceholderText(tr("Search cosmetic catalog"))
        self.favorites_only.setText(tr("Favorites only"))
        selected_category = self.category.currentData()
        selected_hero = self.hero_filter.currentData()
        selected_slot = self.slot_filter.currentData()
        self.category.blockSignals(True)
        self.hero_filter.blockSignals(True)
        self.slot_filter.blockSignals(True)
        self.category.clear()
        self.category.addItem(tr("All categories"), None)
        for value, label in CATEGORY_LABELS.items():
            self.category.addItem(tr(label), value)
        if selected_category is not None:
            index = self.category.findData(selected_category)
            if index >= 0:
                self.category.setCurrentIndex(index)
        self.hero_filter.clear()
        self.hero_filter.addItem(tr("All heroes"), None)
        for hero_id in self._cosmetics.list_hero_ids():
            self.hero_filter.addItem(tr(hero_id), hero_id)
        if selected_hero is not None:
            index = self.hero_filter.findData(selected_hero)
            if index >= 0:
                self.hero_filter.setCurrentIndex(index)
        self.slot_filter.clear()
        self.slot_filter.addItem(tr("All slots"), None)
        for slot in self._cosmetics.list_slots():
            self.slot_filter.addItem(tr(slot), slot)
        if selected_slot is not None:
            index = self.slot_filter.findData(selected_slot)
            if index >= 0:
                self.slot_filter.setCurrentIndex(index)
        self.category.blockSignals(False)
        self.hero_filter.blockSignals(False)
        self.slot_filter.blockSignals(False)
        self.selection_summary.setText(
            tr("Items in my selection: {count}").format(
                count=len(self._cosmetics.list_local_selection())
            )
        )
        self.assign_button.setText(tr("Add to my selection"))
        self.sections.setTabText(0, tr("Catalog"))
        self.sections.setTabText(1, tr("My selection"))
        self.remove_selection_item_button.setText(tr("Remove selected cosmetic"))
        self.refresh_selection_items()
        self.refresh_items()
