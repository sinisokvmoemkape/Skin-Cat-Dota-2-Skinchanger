"""Install the wheel produced by the package smoke workflow."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    wheels = sorted((ROOT / "dist").glob("*.whl"))
    if len(wheels) != 1:
        print(f"Expected exactly one wheel in dist/, found {len(wheels)}", file=sys.stderr)
        return 1
    subprocess.run(
        [sys.executable, "-m", "pip", "install", "--force-reinstall", str(wheels[0])],
        check=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
