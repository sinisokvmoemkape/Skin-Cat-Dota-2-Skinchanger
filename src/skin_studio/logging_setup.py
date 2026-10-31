"""Safe application logging with basic credential redaction."""

from __future__ import annotations

import logging
import re
from pathlib import Path

_SECRET_RE = re.compile(
    r"(?i)\b(api[_-]?key|token|password|cookie|authorization)\b\s*([=:])\s*([^\s,;]+)"
)


class SecretRedactionFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        try:
            message = record.getMessage()
        except Exception:
            message = "<unformattable log message>"
        record.msg = _SECRET_RE.sub(r"\1\2[REDACTED]", message)
        record.args = ()
        return True


def configure_logging(logs_dir: Path) -> logging.Logger:
    logs_dir.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("skin_studio")
    logger.setLevel(logging.INFO)
    logger.propagate = False
    if not logger.handlers:
        handler = logging.FileHandler(logs_dir / "skin-studio.log", encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        handler.addFilter(SecretRedactionFilter())
        logger.addHandler(handler)
    return logger
