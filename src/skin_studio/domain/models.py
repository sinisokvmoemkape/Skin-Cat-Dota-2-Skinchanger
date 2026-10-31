"""Small domain models shared across services and the UI."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from pathlib import Path


@dataclass(frozen=True)
class Hero:
    identifier: str
    name: str
    is_sample: bool = True


@dataclass(frozen=True)
class SteamInstall:
    steam_root: Path
    library_root: Path
    game_path: Path
    compatibility: str


@dataclass(frozen=True)
class Profile:
    identifier: int
    name: str
    created_at: datetime


class CosmeticCategory(StrEnum):
    HERO_ITEM = "hero_item"
    COURIER = "courier"
    WARD = "ward"
    WEATHER = "weather"
    TERRAIN = "terrain"
    MUSIC = "music"
    ANNOUNCER = "announcer"
    HUD = "hud"
    LOADING_SCREEN = "loading_screen"
    TAUNT = "taunt"
    ABILITY_EFFECT = "ability_effect"
    OTHER = "other"


@dataclass(frozen=True)
class CosmeticItem:
    identifier: str
    name: str
    category: str
    hero_id: str | None
    slot: str | None
    source: str
    license_status: str
    is_sample: bool
    is_favorite: bool = False
