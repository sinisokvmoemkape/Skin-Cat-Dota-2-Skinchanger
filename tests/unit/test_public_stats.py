import io
import json
from urllib.error import HTTPError, URLError

import pytest

from skin_studio.services import public_stats
from skin_studio.services.public_stats import (
    PublicStatsError,
    fetch_public_player_stats,
    normalize_account_id,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (" 12345 ", 12345),
        ("76561197960278073", 12345),
    ],
)
def test_normalize_account_id_accepts_steam32_and_steamid64(
    value: str, expected: int
) -> None:
    assert normalize_account_id(value) == expected


@pytest.mark.parametrize("value", ["", "abc", "-1", "0", "999999999999999999999"])
def test_normalize_account_id_rejects_invalid_values(value: str) -> None:
    with pytest.raises(ValueError):
        normalize_account_id(value)


def test_fetch_public_player_stats_uses_profile_and_win_loss_endpoints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    responses = [
        {
            "profile": {"personaname": "<script>Player</script>"},
            "rank_tier": 53,
        },
        {"win": 21, "lose": 9},
    ]
    requested_urls: list[str] = []

    class FakeResponse(io.BytesIO):
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_args: object) -> None:
            self.close()

    def fake_urlopen(request, *, timeout: int) -> FakeResponse:
        assert timeout == public_stats.REQUEST_TIMEOUT_SECONDS
        requested_urls.append(request.full_url)
        return FakeResponse(json.dumps(responses.pop(0)).encode("utf-8"))

    monkeypatch.setattr(public_stats, "urlopen", fake_urlopen)
    stats = fetch_public_player_stats(12345)

    assert stats.account_id == 12345
    assert stats.player_name == "<script>Player</script>"
    assert stats.rank_tier == 53
    assert (stats.wins, stats.losses) == (21, 9)
    assert stats.retrieved_at.utcoffset().total_seconds() == 0
    assert requested_urls == [
        "https://api.opendota.com/api/players/12345",
        "https://api.opendota.com/api/players/12345/wl",
    ]


def test_fetch_public_player_stats_reports_unavailable_profile(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unavailable(*_args: object, **_kwargs: object) -> None:
        raise HTTPError("https://api.opendota.com/api/players/12345", 404, "missing", None, None)

    monkeypatch.setattr(public_stats, "urlopen", unavailable)
    with pytest.raises(PublicStatsError, match="profile_unavailable"):
        fetch_public_player_stats(12345)


def test_fetch_public_player_stats_reports_rate_limit_as_temporary_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def rate_limited(*_args: object, **_kwargs: object) -> None:
        raise HTTPError("https://api.opendota.com/api/players/12345", 429, "limited", None, None)

    monkeypatch.setattr(public_stats, "urlopen", rate_limited)
    with pytest.raises(PublicStatsError, match="service_unavailable"):
        fetch_public_player_stats(12345)


def test_fetch_public_player_stats_reports_network_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def network_error(*_args: object, **_kwargs: object) -> None:
        raise URLError("offline")

    monkeypatch.setattr(public_stats, "urlopen", network_error)
    with pytest.raises(PublicStatsError, match="network_error"):
        fetch_public_player_stats(12345)


def test_fetch_public_player_stats_rejects_oversized_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeResponse(io.BytesIO):
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_args: object) -> None:
            self.close()

    monkeypatch.setattr(
        public_stats,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(b"x" * (public_stats.MAX_RESPONSE_BYTES + 1)),
    )
    with pytest.raises(PublicStatsError, match="invalid_response"):
        fetch_public_player_stats(12345)


@pytest.mark.parametrize(
    ("player_data", "record_data"),
    [
        ([], {"win": 1, "lose": 0}),
        ({"profile": [], "rank_tier": None}, {"win": 1, "lose": 0}),
        ({"profile": {"account_id": 54321}, "rank_tier": None}, {"win": 1, "lose": 0}),
        ({"profile": None, "rank_tier": 90}, {"win": 1, "lose": 0}),
        ({"profile": None, "rank_tier": None}, {"win": -1, "lose": 0}),
        ({"profile": None, "rank_tier": None}, {"win": 1, "lose": True}),
    ],
)
def test_fetch_public_player_stats_rejects_invalid_api_shapes(
    monkeypatch: pytest.MonkeyPatch,
    player_data: object,
    record_data: object,
) -> None:
    responses = iter((player_data, record_data))

    class FakeResponse(io.BytesIO):
        def __enter__(self) -> "FakeResponse":
            return self

        def __exit__(self, *_args: object) -> None:
            self.close()

    monkeypatch.setattr(
        public_stats,
        "urlopen",
        lambda *_args, **_kwargs: FakeResponse(json.dumps(next(responses)).encode("utf-8")),
    )
    with pytest.raises(PublicStatsError, match="invalid_response"):
        fetch_public_player_stats(12345)
