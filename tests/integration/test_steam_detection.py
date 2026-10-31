from pathlib import Path

from skin_studio.services.steam_detection import discover_steam


def _make_install(library: Path, *, proton: bool = False) -> Path:
    steamapps = library / "steamapps"
    game = steamapps / "common" / "dota 2 beta"
    game.mkdir(parents=True)
    (steamapps / "appmanifest_570.acf").write_text('"appid" "570"\n', encoding="utf-8")
    if proton:
        (steamapps / "compatdata" / "570").mkdir(parents=True)
    return game


def test_finds_game_in_multiple_libraries_without_writing(tmp_path: Path) -> None:
    steam_root = tmp_path / "Steam"
    first_library = steam_root
    second_library = tmp_path / "Games Library"
    steam_root.mkdir()
    second_library.mkdir()
    (steam_root / "steamapps").mkdir()
    _make_install(first_library)
    second_game = _make_install(second_library, proton=True)
    vdf = steam_root / "steamapps" / "libraryfolders.vdf"
    vdf.write_text(
        '"libraryfolders" { "0" { "path" "' + str(steam_root) + '" } '
        '"1" { "path" "' + str(second_library) + '" } }',
        encoding="utf-8",
    )
    before = {
        path.relative_to(tmp_path): path.read_bytes() if path.is_file() else None
        for path in tmp_path.rglob("*")
    }

    installs = discover_steam(roots=[steam_root])

    after = {
        path.relative_to(tmp_path): path.read_bytes() if path.is_file() else None
        for path in tmp_path.rglob("*")
    }
    assert len(installs) == 2
    assert any(install.game_path == second_game.resolve() for install in installs)
    assert {install.compatibility for install in installs} == {"Native", "Proton"}
    assert before == after


def test_missing_steam_installation_returns_empty_tuple(tmp_path: Path) -> None:
    assert discover_steam(roots=[tmp_path / "missing"]) == ()


def test_manual_override_is_read_only_and_respects_manifest(tmp_path: Path) -> None:
    steam_root = tmp_path / "Steam"
    steam_root.mkdir()
    _make_install(steam_root)
    result = discover_steam(str(steam_root), platform="linux")
    assert len(result) == 1
    assert result[0].compatibility == "Native"
