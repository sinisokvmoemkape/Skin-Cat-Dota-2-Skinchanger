"""Bounded, versioned profile JSON import/export."""

from __future__ import annotations

import json
import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from skin_studio.domain.errors import InvalidProfileImportError
from skin_studio.domain.models import CosmeticItem, Profile

SCHEMA_VERSION = 1
MAX_IMPORT_BYTES = 1_048_576
MAX_ITEMS_PER_PROFILE = 500
_ITEM_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z")


@dataclass(frozen=True)
class ProfileImportPreview:
    name: str
    item_ids: tuple[str, ...]


def export_profile(profile: Profile, items: tuple[CosmeticItem, ...]) -> bytes:
    document = {
        "schema_version": SCHEMA_VERSION,
        "profile": {
            "name": profile.name,
            "item_ids": [item.identifier for item in items],
        },
    }
    return (json.dumps(document, ensure_ascii=False, indent=2) + "\n").encode("utf-8")


def parse_profile_import(payload: bytes, available_item_ids: set[str]) -> ProfileImportPreview:
    if len(payload) > MAX_IMPORT_BYTES:
        raise InvalidProfileImportError("The selected file exceeds the 1 MiB limit")
    try:
        text = payload.decode("utf-8")
        document = json.loads(text, object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, ValueError, RecursionError) as exc:
        raise InvalidProfileImportError("The selected file is not valid UTF-8 JSON") from exc

    if not isinstance(document, dict) or set(document) != {"schema_version", "profile"}:
        raise InvalidProfileImportError("Unexpected profile document fields")
    if type(document["schema_version"]) is not int or document["schema_version"] != SCHEMA_VERSION:
        raise InvalidProfileImportError("Unsupported profile schema version")
    profile = document["profile"]
    if not isinstance(profile, dict) or set(profile) != {"name", "item_ids"}:
        raise InvalidProfileImportError("Unexpected profile fields")

    name = profile["name"]
    if (
        not isinstance(name, str)
        or not name.strip()
        or len(name.strip()) > 80
        or any(ord(character) < 32 or ord(character) == 127 for character in name.strip())
    ):
        raise InvalidProfileImportError("Profile name must contain between 1 and 80 characters")
    item_ids = profile["item_ids"]
    if not isinstance(item_ids, list) or len(item_ids) > MAX_ITEMS_PER_PROFILE:
        raise InvalidProfileImportError("Profile contains too many cosmetic entries")
    if any(not isinstance(item_id, str) or not _ITEM_ID.fullmatch(item_id) for item_id in item_ids):
        raise InvalidProfileImportError("Profile contains an invalid cosmetic identifier")
    if len(set(item_ids)) != len(item_ids):
        raise InvalidProfileImportError("Profile contains duplicate cosmetic identifiers")
    missing = sorted(set(item_ids) - available_item_ids)
    if missing:
        raise InvalidProfileImportError(
            f"Profile references catalog entries that are unavailable: {', '.join(missing[:5])}"
        )
    return ProfileImportPreview(name.strip(), tuple(item_ids))


def atomic_write(path: Path, payload: bytes) -> None:
    """Write an export atomically beside the user-selected destination."""
    if not path.parent.is_dir():
        raise OSError("The selected destination folder does not exist")
    temporary_name: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{path.name}.", suffix=".tmp", dir=path.parent, delete=False
        ) as stream:
            temporary_name = stream.name
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_name, path)
    finally:
        if temporary_name and os.path.exists(temporary_name):
            os.unlink(temporary_name)


def _unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON field: {key}")
        result[key] = value
    return result
