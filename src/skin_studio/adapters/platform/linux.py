"""Linux Steam installation candidates."""

import os
from collections.abc import Mapping
from pathlib import Path


def steam_roots(
    environ: Mapping[str, str] | None = None, *, home: Path | None = None
) -> tuple[Path, ...]:
    env = os.environ if environ is None else environ
    user_home = Path.home() if home is None else home
    candidates = [
        user_home / ".steam" / "steam",
        user_home / ".local" / "share" / "Steam",
        user_home / ".var" / "app" / "com.valvesoftware.Steam" / ".local" / "share" / "Steam",
    ]
    if env.get("STEAM_DIR"):
        candidates.insert(0, Path(env["STEAM_DIR"]))
    return _existing_unique(candidates)


def _existing_unique(candidates: list[Path]) -> tuple[Path, ...]:
    result: list[Path] = []
    seen: set[Path] = set()
    for candidate in candidates:
        try:
            resolved = candidate.expanduser().resolve(strict=True)
        except (OSError, RuntimeError):
            continue
        if resolved.is_dir() and resolved not in seen:
            seen.add(resolved)
            result.append(resolved)
    return tuple(result)
