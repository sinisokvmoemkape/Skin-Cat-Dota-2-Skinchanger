"""Platform adapter protocol."""

from pathlib import Path
from typing import Protocol


class PlatformPaths(Protocol):
    def steam_roots(self) -> tuple[Path, ...]: ...
