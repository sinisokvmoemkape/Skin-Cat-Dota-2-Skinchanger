import struct
from pathlib import Path

import pytest

from skin_studio.services.vpk_mods import VpkModError, VpkModService


def _vpk(payload: bytes) -> bytes:
    return struct.pack("<III", 0x55AA1234, 1, len(payload)) + payload


def _service(tmp_path: Path) -> tuple[VpkModService, Path, Path, Path]:
    game_root = tmp_path / "dota 2 beta"
    target = game_root / "game" / "dota" / "pak01_dir.vpk"
    source = tmp_path / "downloads" / "custom.vpk"
    backup_root = tmp_path / "app-data" / "vpk-backups"
    target.parent.mkdir(parents=True)
    source.parent.mkdir(parents=True)
    target.write_bytes(_vpk(b"original game vpk"))
    source.write_bytes(_vpk(b"user supplied mod vpk"))
    return VpkModService(game_root, backup_root), source, target, backup_root


def test_apply_creates_backup_and_replaces_only_explicit_target(tmp_path: Path) -> None:
    service, source, target, backup_root = _service(tmp_path)
    other_target = target.parent / "other.vpk"
    other_target.write_bytes(_vpk(b"untouched"))

    backup = service.apply(source, target)

    assert target.read_bytes() == _vpk(b"user supplied mod vpk")
    assert other_target.read_bytes() == _vpk(b"untouched")
    assert backup.backup_file.read_bytes() == _vpk(b"original game vpk")
    assert backup.status == "applied"
    assert backup_root.is_relative_to(tmp_path)
    assert service.list_backups() == (backup,)


def test_restore_restores_original_and_keeps_backup_record(tmp_path: Path) -> None:
    service, source, target, _ = _service(tmp_path)
    backup = service.apply(source, target)

    restored = service.restore(backup.identifier)

    assert target.read_bytes() == _vpk(b"original game vpk")
    assert restored.status == "restored"
    assert restored.backup_file.read_bytes() == _vpk(b"original game vpk")
    assert service.list_backups() == (restored,)


def test_apply_requires_restore_before_replacing_same_target_again(tmp_path: Path) -> None:
    service, source, target, _ = _service(tmp_path)
    service.apply(source, target)

    with pytest.raises(VpkModError, match="Restore the existing backup"):
        service.apply(source, target)


def test_restore_refuses_to_overwrite_a_target_changed_after_apply(tmp_path: Path) -> None:
    service, source, target, _ = _service(tmp_path)
    backup = service.apply(source, target)
    target.write_bytes(_vpk(b"changed by another tool"))

    with pytest.raises(VpkModError, match="refusing to overwrite external changes"):
        service.restore(backup.identifier)

    assert target.read_bytes() == _vpk(b"changed by another tool")


def test_apply_rejects_a_target_outside_selected_game_root(tmp_path: Path) -> None:
    service, source, target, _ = _service(tmp_path)
    outside = tmp_path / "outside.vpk"
    outside.write_bytes(_vpk(b"do not replace"))

    with pytest.raises(VpkModError, match="inside the selected Dota 2 folder"):
        service.apply(source, outside)
    assert outside.read_bytes() == _vpk(b"do not replace")


def test_apply_rejects_missing_or_non_vpk_sources(tmp_path: Path) -> None:
    service, _, target, _ = _service(tmp_path)
    missing = tmp_path / "missing.vpk"
    wrong_extension = tmp_path / "mod.zip"
    wrong_extension.write_bytes(b"not a VPK")

    with pytest.raises(VpkModError, match="source VPK"):
        service.apply(missing, target)
    with pytest.raises(VpkModError, match="\\.vpk extension"):
        service.apply(wrong_extension, target)


def test_apply_rejects_invalid_vpk_header(tmp_path: Path) -> None:
    service, source, target, _ = _service(tmp_path)
    source.write_bytes(b"not a VPK")

    with pytest.raises(VpkModError, match="too small to contain a valid header"):
        service.apply(source, target)


def test_restore_refuses_a_tampered_backup(tmp_path: Path) -> None:
    service, source, target, _ = _service(tmp_path)
    backup = service.apply(source, target)
    backup.backup_file.write_bytes(_vpk(b"tampered backup"))

    with pytest.raises(VpkModError, match="backup file failed its SHA-256 integrity check"):
        service.restore(backup.identifier)


def test_backup_location_must_be_outside_game_root(tmp_path: Path) -> None:
    service, source, target, _ = _service(tmp_path)
    unsafe_service = VpkModService(target.parents[2], target.parent / "backups")

    with pytest.raises(VpkModError, match="outside the Dota 2 folder"):
        unsafe_service.apply(source, target)
