"""Read-only Steam and Dota 2 path discovery."""

from __future__ import annotations

import re
import sys
from collections.abc import Iterable
from pathlib import Path

from skin_studio.adapters.platform import linux, windows
from skin_studio.domain.models import SteamInstall

_LIBRARY_PATH_RE = re.compile(r'"path"\s*"((?:[^"\\]|\\.)*)"')
_MAX_VDF_BYTES = 1_048_576
_DOTA_DIRECTORY = Path("steamapps") / "common" / "dota 2 beta"


def discover_steam(
    override: str | None = None,
    *,
    platform: str | None = None,
    environ: dict[str, str] | None = None,
    home: Path | None = None,
    roots: Iterable[Path] | None = None,
) -> tuple[SteamInstall, ...]:
    """Find installed copies from known roots and Steam libraryfolders.vdf.

    Discovery only reads paths and Steam's libraryfolders.vdf. It never starts Steam,
    opens a game process, or changes installation files.
    """
    system = sys.platform if platform is None else platform
    if roots is not None:
        steam_roots = tuple(Path(root).expanduser() for root in roots)
    elif override:
        steam_roots = (Path(override).expanduser(),)
    elif system.startswith("win"):
        steam_roots = windows.steam_roots(environ, home=home)
    else:
        steam_roots = linux.steam_roots(environ, home=home)

    installs: list[SteamInstall] = []
    seen: set[Path] = set()
    for steam_root in steam_roots:
        resolved_root = _resolved_directory(steam_root)
        if resolved_root is None:
            continue
        for library_root in _library_roots(resolved_root):
            game_path = library_root / _DOTA_DIRECTORY
            manifest = library_root / "steamapps" / "appmanifest_570.acf"
            if not game_path.is_dir() or not manifest.is_file():
                continue
            resolved_game = _resolved_directory(game_path)
            resolved_library = _resolved_directory(library_root)
            if resolved_game is None or resolved_library is None or resolved_game in seen:
                continue
            seen.add(resolved_game)
            compatibility = (
                "Proton"
                if (library_root / "steamapps" / "compatdata" / "570").is_dir()
                else "Native"
            )
            installs.append(
                SteamInstall(
                    steam_root=resolved_root,
                    library_root=resolved_library,
                    game_path=resolved_game,
                    compatibility=compatibility,
                )
            )
    return tuple(installs)


def _resolved_directory(path: Path) -> Path | None:
    try:
        resolved = path.resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return resolved if resolved.is_dir() else None


def _library_roots(steam_root: Path) -> tuple[Path, ...]:
    candidates = [steam_root]
    vdf_path = steam_root / "steamapps" / "libraryfolders.vdf"
    try:
        if vdf_path.stat().st_size <= _MAX_VDF_BYTES:
            content = vdf_path.read_text(encoding="utf-8", errors="strict")
            for raw_path in _LIBRARY_PATH_RE.findall(content):
                decoded = raw_path.replace("\\\\", "\\").replace('\\"', '"')
                candidates.append(Path(decoded))
    except (OSError, UnicodeError):
        pass

    result: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        resolved = _resolved_directory(candidate)
        if resolved is not None and resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return tuple(result)
