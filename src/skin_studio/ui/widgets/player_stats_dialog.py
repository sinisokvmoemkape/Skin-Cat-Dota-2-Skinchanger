"""A manual, historical public-profile lookup dialog."""

from __future__ import annotations

from PySide6.QtCore import QObject, QRunnable, Qt, QThreadPool, Signal, Slot
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from skin_studio.i18n.manager import LanguageManager
from skin_studio.services.public_stats import (
    PublicPlayerStats,
    PublicStatsError,
    fetch_public_player_stats,
    normalize_account_id,
)


def tr(source: str) -> str:
    return LanguageManager.text(source)


class _LookupSignals(QObject):
    succeeded = Signal(object)
    failed = Signal(str)
    finished = Signal()


class _LookupTask(QRunnable):
    def __init__(self, account_id: int) -> None:
        super().__init__()
        self.account_id = account_id
        self.signals = _LookupSignals()

    @Slot()
    def run(self) -> None:
        try:
            self.signals.succeeded.emit(fetch_public_player_stats(self.account_id))
        except PublicStatsError as error:
            self.signals.failed.emit(error.code)
        finally:
            self.signals.finished.emit()


class PlayerStatsDialog(QDialog):
    """Fetches only after an explicit user action; no IDs or responses are persisted."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._task: _LookupTask | None = None
        self.setMinimumWidth(480)

        layout = QVBoxLayout(self)
        self.title = QLabel()
        self.title.setObjectName("sectionTitle")
        self.description = QLabel()
        self.description.setWordWrap(True)
        self.account_id_label = QLabel()
        self.account_id = QLineEdit()
        self.account_id.setMaxLength(20)
        self.account_id.setClearButtonEnabled(True)
        self.lookup_button = QPushButton()
        self.lookup_button.setObjectName("primaryButton")
        self.lookup_button.clicked.connect(self._lookup)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.result_label = QLabel()
        self.result_label.setObjectName("overlayCardText")
        self.result_label.setTextFormat(Qt.TextFormat.PlainText)
        self.result_label.setWordWrap(True)
        self.source_note = QLabel()
        self.source_note.setWordWrap(True)
        self.source_note.setOpenExternalLinks(True)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        self.buttons.rejected.connect(self.reject)

        form = QFormLayout()
        form.addRow(self.account_id_label, self.account_id)
        layout.addWidget(self.title)
        layout.addWidget(self.description)
        layout.addLayout(form)
        layout.addWidget(self.lookup_button)
        layout.addWidget(self.status)
        layout.addWidget(self.result_label)
        layout.addWidget(self.source_note)
        layout.addWidget(self.buttons)
        self.retranslate()

    def retranslate(self) -> None:
        self.setWindowTitle(tr("Public player history"))
        self.title.setText(tr("Public player history"))
        self.description.setText(
            tr(
                "Enter a Steam32 account ID or SteamID64 for a manual lookup. "
                "Only historical public profile totals are requested; no match roster or "
                "live game state is accessed."
            )
        )
        self.account_id_label.setText(tr("Steam account ID"))
        self.account_id.setPlaceholderText(tr("Steam32 ID or SteamID64"))
        self.lookup_button.setText(tr("Look up public history"))
        self.source_note.setText(
            tr(
                'Source: <a href="https://www.opendota.com/terms">OpenDota API</a>. '
                "The ID is sent only after you submit it and is not saved. "
                "Data availability and freshness depend on the provider."
            )
        )

    @Slot()
    def _lookup(self) -> None:
        try:
            account_id = normalize_account_id(self.account_id.text())
        except ValueError:
            self.result_label.clear()
            self.status.setText(tr("Enter a valid numeric Steam account ID."))
            return

        self.result_label.clear()
        self.status.setText(tr("Loading public historical data…"))
        self.lookup_button.setEnabled(False)
        self.account_id.setEnabled(False)
        task = _LookupTask(account_id)
        task.signals.succeeded.connect(self._show_result)
        task.signals.failed.connect(self._show_error)
        task.signals.finished.connect(self._finish_lookup)
        self._task = task
        QThreadPool.globalInstance().start(task)

    @Slot(object)
    def _show_result(self, result: object) -> None:
        if not isinstance(result, PublicPlayerStats):
            self._show_error("invalid_response")
            return
        total_games = result.wins + result.losses
        win_rate = f"{result.wins / total_games * 100:.1f}" if total_games else "—"
        player_name = result.player_name or tr("Unavailable")
        rank = _rank_label(result.rank_tier)
        retrieved_at = result.retrieved_at.strftime("%Y-%m-%d %H:%M")
        self.result_label.setText(
            tr(
                "Profile: {name}\n"
                "Rank: {rank}\n"
                "All-time wins: {wins}\n"
                "All-time losses: {losses}\n"
                "Games indexed: {games}\n"
                "Win rate: {rate}%\n"
                "Steam32 account ID: {account_id}\n"
                "Retrieved (UTC): {retrieved_at}\n"
                "Source: OpenDota"
            ).format(
                name=player_name,
                rank=rank,
                wins=result.wins,
                losses=result.losses,
                games=total_games,
                rate=win_rate,
                account_id=result.account_id,
                retrieved_at=retrieved_at,
            )
        )
        self.status.setText(tr("Public profile data loaded."))

    @Slot(str)
    def _show_error(self, code: str) -> None:
        messages = {
            "profile_unavailable": "Public profile or match-history data is unavailable.",
            "service_unavailable": "OpenDota is temporarily unavailable. Try again later.",
            "network_error": "Could not connect to OpenDota. Check your connection and retry.",
            "invalid_response": "OpenDota returned data in an unexpected format.",
        }
        self.result_label.clear()
        self.status.setText(tr(messages.get(code, "Could not load public profile data.")))

    @Slot()
    def _finish_lookup(self) -> None:
        self.lookup_button.setEnabled(True)
        self.account_id.setEnabled(True)
        self._task = None


def _rank_label(rank_tier: int | None) -> str:
    if rank_tier is None or rank_tier == 0:
        return tr("Unavailable")
    medals = {
        10: "Herald",
        20: "Guardian",
        30: "Crusader",
        40: "Archon",
        50: "Legend",
        60: "Ancient",
        70: "Divine",
        80: "Immortal",
    }
    medal = rank_tier // 10 * 10
    label = medals.get(medal)
    if label is None:
        return tr("Unavailable")
    translated = tr(label)
    stars = rank_tier % 10
    return f"{translated} {stars}" if medal < 80 and 1 <= stars <= 5 else translated
