"""Application paths and user preferences."""

from __future__ import annotations

import json
import locale
import os
import tempfile
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path

APP_ID = "dota-2-skin-studio"
SETTINGS_VERSION = 1
DEFAULT_HOTKEY = "Ctrl+Shift+O"


@dataclass(frozen=True)
class AppPaths:
    data_dir: Path
    config_dir: Path
    cache_dir: Path

    @property
    def database(self) -> Path:
        return self.data_dir / "skin-studio.sqlite3"

    @property
    def settings(self) -> Path:
        return self.config_dir / "settings.json"

    @property
    def logs_dir(self) -> Path:
        return self.cache_dir / "logs"


@dataclass
class Settings:
    language: str | None = None
    steam_path: str | None = None
    hotkey: str = DEFAULT_HOTKEY


def is_valid_hotkey(value: str) -> bool:
    """Accept one portable key chord with a non-shift modifier and one key."""
    if not isinstance(value, str) or len(value) > 40:
        return False
    parts = value.split("+")
    if len(parts) < 2:
        return False
    modifiers = {"ctrl", "alt", "shift", "meta"}
    normalized = [part.casefold() for part in parts]
    if any(part not in modifiers for part in normalized[:-1]):
        return False
    if len(set(normalized[:-1])) != len(normalized[:-1]):
        return False
    if not set(normalized[:-1]) & {"ctrl", "alt", "meta"}:
        return False
    key = normalized[-1]
    valid_key = (len(key) == 1 and key.isascii() and key.isalnum()) or (
        key.startswith("f") and key[1:].isdigit() and 1 <= int(key[1:]) <= 24
    )
    return valid_key and key not in modifiers


def app_paths(
    environ: Mapping[str, str] | None = None,
    *,
    system: str | None = None,
    home: Path | None = None,
) -> AppPaths:
    """Return per-user paths without creating them."""
    env = os.environ if environ is None else environ
    platform = os.name if system is None else system
    user_home = Path.home() if home is None else home

    if platform == "nt":
        roaming = Path(env.get("APPDATA", user_home / "AppData" / "Roaming"))
        local = Path(env.get("LOCALAPPDATA", user_home / "AppData" / "Local"))
        return AppPaths(
            data_dir=local / APP_ID / "data",
            config_dir=roaming / APP_ID,
            cache_dir=local / APP_ID / "cache",
        )

    data_home = Path(env.get("XDG_DATA_HOME", user_home / ".local" / "share"))
    config_home = Path(env.get("XDG_CONFIG_HOME", user_home / ".config"))
    cache_home = Path(env.get("XDG_CACHE_HOME", user_home / ".cache"))
    defaults = (
        user_home / ".local" / "share",
        user_home / ".config",
        user_home / ".cache",
    )
    data_home, config_home, cache_home = (
        candidate if candidate.is_absolute() else default
        for candidate, default in zip((data_home, config_home, cache_home), defaults, strict=True)
    )
    return AppPaths(
        data_dir=data_home / APP_ID,
        config_dir=config_home / APP_ID,
        cache_dir=cache_home / APP_ID,
    )


def system_language() -> str:
    """Choose a supported language from the current OS locale."""
    current = locale.getlocale()[0] or ""
    return "ru" if current.casefold().startswith("ru") else "en"


def load_settings(path: Path) -> Settings:
    if not path.exists():
        return Settings()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("Settings file is unreadable or malformed") from exc
    if not isinstance(raw, dict) or raw.get("version") != SETTINGS_VERSION:
        raise ValueError("Unsupported settings file format")
    language = raw.get("language")
    steam_path = raw.get("steam_path")
    hotkey = raw.get("hotkey", DEFAULT_HOTKEY)
    if language not in (None, "en", "ru"):
        raise ValueError("Unsupported language setting")
    if steam_path is not None and (not isinstance(steam_path, str) or len(steam_path) > 4096):
        raise ValueError("Invalid Steam path setting")
    if not is_valid_hotkey(hotkey):
        raise ValueError("Invalid global shortcut setting")
    return Settings(language=language, steam_path=steam_path, hotkey=hotkey)


def save_settings(path: Path, settings: Settings) -> None:
    if settings.language not in (None, "en", "ru"):
        raise ValueError("Unsupported language setting")
    if settings.steam_path is not None and len(settings.steam_path) > 4096:
        raise ValueError("Steam path setting is too long")
    if not is_valid_hotkey(settings.hotkey):
        raise ValueError("Invalid global shortcut setting")
    payload = {"version": SETTINGS_VERSION, **asdict(settings)}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", dir=path.parent, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(payload, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        temporary_path.replace(path)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
