"""Manual lookups of public, historical player aggregates from OpenDota."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from http.client import HTTPException
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

STEAM_ID64_BASE = 76_561_197_960_265_728
MAX_RESPONSE_BYTES = 256 * 1024
REQUEST_TIMEOUT_SECONDS = 8
_API_ROOT = "https://api.opendota.com/api"


class PublicStatsError(Exception):
    """A user-displayable failure while retrieving public stats."""

    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class PublicPlayerStats:
    account_id: int
    player_name: str | None
    rank_tier: int | None
    wins: int
    losses: int
    retrieved_at: datetime


def normalize_account_id(value: str) -> int:
    """Accept a Steam32 account ID or a SteamID64 and return the Steam32 ID."""
    normalized = value.strip()
    if not normalized.isascii() or not normalized.isdecimal():
        raise ValueError("invalid_account_id")
    identifier = int(normalized)
    if 1 <= identifier <= 4_294_967_295:
        return identifier
    account_id = identifier - STEAM_ID64_BASE
    if 1 <= account_id <= 4_294_967_295:
        return account_id
    raise ValueError("invalid_account_id")


def fetch_public_player_stats(account_id: int) -> PublicPlayerStats:
    """Fetch one manually selected profile and its public all-time win/loss totals."""
    if not 1 <= account_id <= 4_294_967_295:
        raise ValueError("invalid_account_id")

    player_data = _get_json(f"{_API_ROOT}/players/{account_id}")
    record_data = _get_json(f"{_API_ROOT}/players/{account_id}/wl")
    if not isinstance(player_data, dict) or not isinstance(record_data, dict):
        raise PublicStatsError("invalid_response")

    profile = player_data.get("profile")
    if profile is not None and not isinstance(profile, dict):
        raise PublicStatsError("invalid_response")
    if profile is not None:
        returned_id = profile.get("account_id")
        if returned_id is not None and (
            isinstance(returned_id, bool)
            or not isinstance(returned_id, int)
            or returned_id != account_id
        ):
            raise PublicStatsError("invalid_response")

    rank_tier = player_data.get("rank_tier")
    if rank_tier is not None and (
        isinstance(rank_tier, bool)
        or not isinstance(rank_tier, int)
        or not 0 <= rank_tier <= 80
    ):
        raise PublicStatsError("invalid_response")

    wins = _non_negative_integer(record_data.get("win"))
    losses = _non_negative_integer(record_data.get("lose"))
    if wins is None or losses is None:
        raise PublicStatsError("invalid_response")

    player_name = None
    if profile is not None:
        candidate_name = profile.get("personaname") or profile.get("name")
        if isinstance(candidate_name, str):
            player_name = _safe_display_name(candidate_name)

    return PublicPlayerStats(
        account_id=account_id,
        player_name=player_name,
        rank_tier=rank_tier,
        wins=wins,
        losses=losses,
        retrieved_at=datetime.now(UTC),
    )


def _get_json(url: str) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "SkinCat/0.1 (manual public profile lookup)",
        },
    )
    try:
        with urlopen(request, timeout=REQUEST_TIMEOUT_SECONDS) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except HTTPError as error:
        if error.code == 429 or error.code >= 500:
            raise PublicStatsError("service_unavailable") from error
        if 400 <= error.code < 500:
            raise PublicStatsError("profile_unavailable") from error
        raise PublicStatsError("network_error") from error
    except HTTPException as error:
        raise PublicStatsError("network_error") from error
    except (TimeoutError, URLError, OSError) as error:
        raise PublicStatsError("network_error") from error

    if len(body) > MAX_RESPONSE_BYTES:
        raise PublicStatsError("invalid_response")
    try:
        return json.loads(body)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise PublicStatsError("invalid_response") from error


def _non_negative_integer(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _safe_display_name(value: str) -> str:
    return "".join(character for character in value if character.isprintable())[:100].strip()
