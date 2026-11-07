import struct
from pathlib import Path

from PySide6.QtTest import QTest
from PySide6.QtWidgets import QMessageBox

from skin_studio.ui.widgets.vpk_mod_dialog import VpkModDialog


def _write_vpk(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(struct.pack("<III", 0x55AA1234, 1, len(payload)) + payload)


def test_vpk_dialog_applies_in_worker_and_lists_backup(
    qapp, tmp_path: Path, monkeypatch
) -> None:
    game_root = tmp_path / "dota 2 beta"
    target = game_root / "game" / "dota" / "pak01_dir.vpk"
    source = tmp_path / "downloads" / "mod.vpk"
    _write_vpk(target, b"original")
    _write_vpk(source, b"replacement")
    dialog = VpkModDialog(
        None,
        backup_root=tmp_path / "app-data" / "vpk-backups",
        is_game_running=lambda: False,
        initial_game_root=game_root,
    )
    dialog.source_path.setText(str(source))
    dialog.target_path.setText(str(target))
    monkeypatch.setattr(
        QMessageBox,
        "question",
        lambda *args, **kwargs: QMessageBox.StandardButton.Yes,
    )

    dialog._apply()
    assert dialog._operation_thread is not None
    for _ in range(250):
        if dialog._operation_thread is None:
            break
        QTest.qWait(20)

    assert dialog._operation_thread is None
    assert target.read_bytes() == source.read_bytes()
    assert dialog.backups.count() == 1
    assert "VPK replaced" in dialog.status.text()
    dialog.close()


def test_vpk_dialog_refuses_apply_and_restore_while_game_is_running(
    qapp, tmp_path: Path, monkeypatch
) -> None:
    game_root = tmp_path / "dota 2 beta"
    _write_vpk(game_root / "game" / "dota" / "target.vpk", b"original")
    _write_vpk(tmp_path / "mod.vpk", b"replacement")
    warnings: list[str] = []
    monkeypatch.setattr(
        QMessageBox,
        "warning",
        lambda _parent, _title, message: warnings.append(message),
    )
    dialog = VpkModDialog(
        None,
        backup_root=tmp_path / "app-data" / "vpk-backups",
        is_game_running=lambda: True,
        initial_game_root=game_root,
    )
    dialog.source_path.setText(str(tmp_path / "mod.vpk"))
    dialog.target_path.setText(str(game_root / "game" / "dota" / "target.vpk"))

    dialog._apply()
    dialog._restore()

    assert len(warnings) == 2
    assert dialog._operation_thread is None
    assert not (tmp_path / "app-data" / "vpk-backups").exists()
    dialog.close()
