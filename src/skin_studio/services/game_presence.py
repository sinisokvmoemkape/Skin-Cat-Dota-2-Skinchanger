"""Read-only detection of whether the Dota 2 executable is running."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

import psutil

DOTA_PROCESS_NAMES = frozenset({"dota2", "dota2.exe"})
ProcessIterator = Callable[..., Iterable[Any]]


class GamePresenceService:
    """Check process names only; never inspect command lines, memory, or game state."""

    def __init__(self, process_iter: ProcessIterator = psutil.process_iter) -> None:
        self._process_iter = process_iter

    def is_dota_running(self) -> bool:
        try:
            processes = self._process_iter(attrs=["name"], ad_value=None)
            for process in processes:
                try:
                    process_name = process.info.get("name")
                except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess):
                    continue
                if isinstance(process_name, str) and process_name.casefold() in DOTA_PROCESS_NAMES:
                    return True
        except (psutil.AccessDenied, psutil.NoSuchProcess, psutil.ZombieProcess, OSError):
            return False
        return False
