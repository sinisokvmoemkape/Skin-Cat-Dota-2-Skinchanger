from datetime import UTC, datetime

from PySide6.QtCore import Qt, QThreadPool

from skin_studio.services.public_stats import PublicPlayerStats
from skin_studio.ui.widgets.player_stats_dialog import PlayerStatsDialog, _rank_label


def test_invalid_manual_id_is_reported_without_requesting_data(qapp) -> None:
    dialog = PlayerStatsDialog()
    dialog.account_id.setText("not-an-id")

    dialog._lookup()

    assert dialog.status.text() == "Enter a valid numeric Steam account ID."
    assert dialog.result_label.text() == ""
    assert dialog.lookup_button.isEnabled()


def test_results_are_rendered_as_plain_text(qapp) -> None:
    dialog = PlayerStatsDialog()
    result = PublicPlayerStats(
        account_id=12345,
        player_name="<img src=x onerror=alert(1)>",
        rank_tier=53,
        wins=21,
        losses=9,
        retrieved_at=datetime(2026, 10, 31, 0, 0, tzinfo=UTC),
    )

    dialog._show_result(result)

    assert dialog.result_label.textFormat() == Qt.TextFormat.PlainText
    assert "<img src=x onerror=alert(1)>" in dialog.result_label.text()
    assert "Games indexed: 30" in dialog.result_label.text()
    assert "Win rate: 70.0%" in dialog.result_label.text()
    assert dialog.status.text() == "Public profile data loaded."


def test_rank_labels_cover_medals_and_unavailable_values(qapp) -> None:
    assert _rank_label(53) == "Legend 3"
    assert _rank_label(80) == "Immortal"
    assert _rank_label(None) == "Unavailable"


def test_lookup_runs_in_background_and_renders_result(
    qapp, monkeypatch
) -> None:
    def fake_fetch(account_id: int) -> PublicPlayerStats:
        return PublicPlayerStats(
            account_id=account_id,
            player_name="Test player",
            rank_tier=None,
            wins=4,
            losses=2,
            retrieved_at=datetime(2026, 10, 31, 0, 0, tzinfo=UTC),
        )

    monkeypatch.setattr(
        "skin_studio.ui.widgets.player_stats_dialog.fetch_public_player_stats", fake_fetch
    )
    dialog = PlayerStatsDialog()
    dialog.account_id.setText("12345")

    dialog._lookup()
    assert not dialog.lookup_button.isEnabled()
    assert QThreadPool.globalInstance().waitForDone(3000)
    qapp.processEvents()

    assert "Test player" in dialog.result_label.text()
    assert dialog.lookup_button.isEnabled()
