"""Windows Steam installation candidates."""

import os
from collections.abc import Mapping
from pathlib import Path


def steam_roots(
    environ: Mapping[str, str] | None = None, *, home: Path | None = None
) -> tuple[Path, ...]:
    env = os.environ if environ is None else environ
    user_home = Path.home() if home is None else home
    candidates: list[Path] = []
    for key in ("STEAM_DIR",):
        if env.get(key):
            candidates.append(Path(env[key]))
    if env.get("ProgramFiles(x86)"):
        candidates.append(Path(env["ProgramFiles(x86)"]) / "Steam")
    if env.get("ProgramFiles"):
        candidates.append(Path(env["ProgramFiles"]) / "Steam")
    if env.get("LOCALAPPDATA"):
        candidates.append(Path(env["LOCALAPPDATA"]) / "Steam")
    candidates.append(user_home / "AppData" / "Local" / "Steam")
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
