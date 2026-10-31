"""Compile Qt Linguist TS catalogs to QM files."""

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCALE_ROOT = ROOT / "src" / "skin_studio" / "i18n" / "locale"


def main() -> int:
    venv_bin = Path(sys.executable).parent
    local_compiler = venv_bin / (
        "pyside6-lrelease.exe" if sys.platform == "win32" else "pyside6-lrelease"
    )
    compiler = (
        shutil.which("pyside6-lrelease")
        or shutil.which("lrelease")
        or (str(local_compiler) if local_compiler.is_file() else None)
    )
    if compiler is None:
        print(
            "Qt Linguist lrelease was not found. Install project dependencies first.",
            file=sys.stderr,
        )
        return 1
    catalogs = sorted(LOCALE_ROOT.glob("*/skin_studio.ts"))
    if not catalogs:
        print("No translation catalogs were found.", file=sys.stderr)
        return 1
    for catalog in catalogs:
        output = catalog.with_suffix(".qm")
        subprocess.run(
            [compiler, "-fail-on-unfinished", str(catalog), "-qm", str(output)],
            check=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
