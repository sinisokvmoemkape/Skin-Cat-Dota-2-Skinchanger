"""Explicit local VPK replacement with per-target backups and guarded restore."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import stat
import struct
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class VpkModError(Exception):
    """Raised when a VPK operation fails validation or cannot be completed safely."""


@dataclass(frozen=True)
class VpkBackup:
    identifier: str
    target: Path
    source_name: str
    backup_file: Path
    manifest_file: Path
    original_sha256: str
    applied_sha256: str
    status: str


class VpkModService:
    _VPK_SIGNATURE = 0x55AA1234

    def __init__(self, game_root: Path, backup_root: Path) -> None:
        self._game_root = game_root
        self._backup_root = backup_root

    def list_backups(self) -> tuple[VpkBackup, ...]:
        if not self._backup_root.exists():
            return ()
        if self._backup_root.is_symlink() or not self._backup_root.is_dir():
            raise VpkModError("The VPK backup location is not a regular directory")
        backups = [
            self._read_backup(manifest)
            for manifest in sorted(self._backup_root.glob("*.json"))
        ]
        return tuple(sorted(backups, key=lambda backup: backup.identifier, reverse=True))

    def apply(self, source: Path, target: Path) -> VpkBackup:
        source_path, target_path = self._validate_paths(source, target)
        backup_root = self._validated_backup_root()
        backup_root.mkdir(mode=0o700, parents=True, exist_ok=True)
        backup_root.chmod(0o700)

        for existing in self.list_backups():
            if existing.target == target_path and existing.status in {"pending", "applied"}:
                raise VpkModError(
                    "Restore the existing backup for this target before applying again"
                )

        _validate_vpk_header(source_path)
        _validate_vpk_header(target_path)
        original_hash = _sha256_file(target_path)
        source_hash = _sha256_file(source_path)
        identifier = uuid.uuid4().hex
        backup_file = backup_root / f"{identifier}.vpk"
        manifest_file = backup_root / f"{identifier}.json"

        _copy_atomic(target_path, backup_file, preserve_mode=False)
        if _sha256_file(backup_file) != original_hash:
            backup_file.unlink(missing_ok=True)
            raise VpkModError("The VPK backup failed its SHA-256 integrity check")
        backup_record = VpkBackup(
            identifier=identifier,
            target=target_path,
            source_name=source_path.name,
            backup_file=backup_file,
            manifest_file=manifest_file,
            original_sha256=original_hash,
            applied_sha256=source_hash,
            status="pending",
        )
        _write_manifest(backup_record)

        try:
            _copy_atomic(source_path, target_path, preserve_mode=True)
        except OSError as exc:
            raise VpkModError(
                f"VPK replacement failed; the original backup was retained: {exc}"
            ) from exc

        applied_record = VpkBackup(
            **{**backup_record.__dict__, "status": "applied"}
        )
        _write_manifest(applied_record)
        return applied_record

    def restore(self, identifier: str) -> VpkBackup:
        if not identifier.isascii() or not identifier.isalnum():
            raise VpkModError("Invalid backup identifier")
        manifest_file = self._validated_backup_root() / f"{identifier}.json"
        backup = self._read_backup(manifest_file)
        if backup.status not in {"pending", "applied"}:
            raise VpkModError("This VPK backup has already been restored")

        game_root = self._validated_game_root()
        target = _resolved_file(backup.target)
        backup_file = _resolved_file(backup.backup_file)
        if target is None or backup_file is None:
            raise VpkModError("The game target or backup file is unavailable")
        if not _is_relative_to(target, game_root):
            raise VpkModError("The VPK target is outside the selected Dota 2 folder")
        if _is_relative_to(backup_file, game_root):
            raise VpkModError("The backup must remain outside the Dota 2 folder")
        if _sha256_file(backup_file) != backup.original_sha256:
            raise VpkModError("The backup file failed its SHA-256 integrity check")

        current_hash = _sha256_file(target)
        if current_hash == backup.original_sha256:
            pass
        elif current_hash == backup.applied_sha256:
            try:
                _copy_atomic(backup_file, target, preserve_mode=True)
            except OSError as exc:
                raise VpkModError(f"VPK restore failed; the backup was retained: {exc}") from exc
        else:
            raise VpkModError(
                "The target VPK changed after installation; refusing to overwrite external changes"
            )

        restored = VpkBackup(**{**backup.__dict__, "status": "restored"})
        _write_manifest(restored)
        return restored

    def _validate_paths(self, source: Path, target: Path) -> tuple[Path, Path]:
        game_root = self._validated_game_root()
        source_path = _resolved_file(source)
        target_path = _resolved_file(target)
        if source_path is None:
            raise VpkModError("Select an existing, regular source VPK file")
        if target_path is None:
            raise VpkModError("Select an existing, regular target VPK file")
        if source_path.suffix.casefold() != ".vpk" or target_path.suffix.casefold() != ".vpk":
            raise VpkModError("Both source and target files must use the .vpk extension")
        if not _is_relative_to(target_path, game_root):
            raise VpkModError("The target VPK must be inside the selected Dota 2 folder")
        if source_path == target_path:
            raise VpkModError("The source and target VPK files must be different")
        return source_path, target_path

    def _validated_backup_root(self) -> Path:
        game_root = self._validated_game_root()
        backup_root = self._backup_root.expanduser().resolve(strict=False)
        if _is_relative_to(backup_root, game_root):
            raise VpkModError("VPK backups must be stored outside the Dota 2 folder")
        return backup_root

    def _validated_game_root(self) -> Path:
        game_root = _resolved_directory(self._game_root)
        if game_root is None or not (game_root / "game").is_dir():
            raise VpkModError("Select the Dota 2 installation folder containing its game directory")
        return game_root

    def _read_backup(self, manifest_file: Path) -> VpkBackup:
        if manifest_file.is_symlink() or not manifest_file.is_file():
            raise VpkModError("A VPK backup manifest is not a regular file")
        try:
            payload = json.loads(manifest_file.read_text(encoding="utf-8"))
            if not isinstance(payload, dict) or set(payload) != {
                "identifier",
                "target",
                "source_name",
                "backup_file",
                "original_sha256",
                "applied_sha256",
                "status",
            }:
                raise ValueError("Unexpected manifest fields")
            identifier = payload["identifier"]
            if (
                not isinstance(identifier, str)
                or not identifier.isascii()
                or not identifier.isalnum()
                or manifest_file.name != f"{identifier}.json"
            ):
                raise ValueError("Invalid backup identifier")
            target = _manifest_path(payload["target"])
            backup_file = _manifest_path(payload["backup_file"])
            source_name = payload["source_name"]
            original_hash = payload["original_sha256"]
            applied_hash = payload["applied_sha256"]
            status = payload["status"]
            if (
                not isinstance(source_name, str)
                or Path(source_name).name != source_name
                or not _is_sha256(original_hash)
                or not _is_sha256(applied_hash)
                or status not in {"pending", "applied", "restored"}
            ):
                raise ValueError("Invalid backup metadata")
            if backup_file != self._validated_backup_root() / f"{identifier}.vpk":
                raise ValueError("Backup file path does not match its identifier")
        except (OSError, UnicodeError, json.JSONDecodeError, TypeError, ValueError) as exc:
            raise VpkModError(f"Invalid VPK backup manifest: {manifest_file.name}") from exc
        return VpkBackup(
            identifier=identifier,
            target=target,
            source_name=source_name,
            backup_file=backup_file,
            manifest_file=manifest_file,
            original_sha256=original_hash,
            applied_sha256=applied_hash,
            status=status,
        )


def _resolved_directory(path: Path) -> Path | None:
    try:
        resolved = path.expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return resolved if resolved.is_dir() else None


def _resolved_file(path: Path) -> Path | None:
    try:
        if path.is_symlink():
            return None
        resolved = path.expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    return resolved if resolved.is_file() else None


def _is_relative_to(path: Path, parent: Path) -> bool:
    try:
        path.relative_to(parent)
    except ValueError:
        return False
    return True


def _sha256_file(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _validate_vpk_header(path: Path) -> None:
    try:
        with path.open("rb") as stream:
            header = stream.read(12)
    except OSError as exc:
        raise VpkModError(f"Unable to read VPK file {path.name}: {exc}") from exc
    if len(header) < 12:
        raise VpkModError(f"VPK file is too small to contain a valid header: {path.name}")
    signature, version, _tree_size = struct.unpack("<III", header)
    if signature != VpkModService._VPK_SIGNATURE or version not in {1, 2}:
        raise VpkModError(f"VPK header is invalid or unsupported: {path.name}")


def _is_sha256(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        int(value, 16)
    except ValueError:
        return False
    return True


def _manifest_path(value: Any) -> Path:
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise ValueError("Expected an absolute path")
    return Path(value)


def _copy_atomic(source: Path, destination: Path, *, preserve_mode: bool) -> None:
    mode = stat.S_IMODE(destination.stat().st_mode) if preserve_mode else None
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{destination.name}.", suffix=".tmp",
            dir=destination.parent, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            with source.open("rb") as source_stream:
                shutil.copyfileobj(source_stream, temporary, length=1024 * 1024)
            temporary.flush()
            os.fsync(temporary.fileno())
        if mode is not None:
            temporary_path.chmod(mode)
        os.replace(temporary_path, destination)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()


def _write_manifest(backup: VpkBackup) -> None:
    document = {
        "identifier": backup.identifier,
        "target": str(backup.target),
        "source_name": backup.source_name,
        "backup_file": str(backup.backup_file),
        "original_sha256": backup.original_sha256,
        "applied_sha256": backup.applied_sha256,
        "status": backup.status,
    }
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", prefix=f".{backup.identifier}.", suffix=".tmp",
            dir=backup.manifest_file.parent, delete=False
        ) as temporary:
            temporary_path = Path(temporary.name)
            json.dump(document, temporary, ensure_ascii=False, indent=2)
            temporary.write("\n")
            temporary.flush()
            os.fsync(temporary.fileno())
        os.replace(temporary_path, backup.manifest_file)
    finally:
        if temporary_path is not None and temporary_path.exists():
            temporary_path.unlink()
