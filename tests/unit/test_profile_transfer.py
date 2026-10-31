from datetime import UTC, datetime
from pathlib import Path

import pytest

from skin_studio.domain.errors import InvalidProfileImportError
from skin_studio.domain.models import CosmeticItem, Profile
from skin_studio.services.profile_transfer import (
    MAX_IMPORT_BYTES,
    atomic_write,
    export_profile,
    parse_profile_import,
)


def test_export_import_round_trip(tmp_path: Path) -> None:
    profile = Profile(7, "Мой профиль", datetime.now(UTC))
    item = CosmeticItem(
        "sample-courier", "Example courier", "courier", None, None, "sample", "not_applicable", True
    )
    payload = export_profile(profile, (item,))
    preview = parse_profile_import(payload, {item.identifier})
    assert preview.name == profile.name
    assert preview.item_ids == (item.identifier,)
    destination = tmp_path / "profile.json"
    atomic_write(destination, payload)
    assert destination.read_bytes() == payload
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize(
    "payload,available,match",
    [
        (b"{bad", set(), "valid UTF-8 JSON"),
        (b'{"schema_version":true,"profile":{}}', set(), "schema version"),
        (
            b'{"schema_version":1,"schema_version":1,"profile":{"name":"x","item_ids":[]}}',
            set(),
            "valid UTF-8 JSON",
        ),
        (
            b'{"schema_version":1,"profile":{"name":"x","item_ids":["missing"]}}',
            set(),
            "unavailable",
        ),
        (
            b'{"schema_version":1,"profile":{"name":"x","item_ids":["a","a"]}}',
            {"a"},
            "duplicate",
        ),
    ],
)
def test_invalid_profile_imports_are_rejected(
    payload: bytes, available: set[str], match: str
) -> None:
    with pytest.raises(InvalidProfileImportError, match=match):
        parse_profile_import(payload, available)


def test_oversized_profile_import_is_rejected() -> None:
    with pytest.raises(InvalidProfileImportError, match="1 MiB"):
        parse_profile_import(b" " * (MAX_IMPORT_BYTES + 1), set())
