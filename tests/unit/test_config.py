from pathlib import Path

import pytest

from skin_studio.config import Settings, app_paths, load_settings, save_settings


def test_linux_paths_respect_xdg_and_unicode_home(tmp_path: Path) -> None:
    paths = app_paths(
        {
            "XDG_DATA_HOME": "/tmp/данные",
            "XDG_CONFIG_HOME": "/tmp/настройки",
            "XDG_CACHE_HOME": "/tmp/кэш",
        },
        system="posix",
        home=tmp_path,
    )
    assert paths.data_dir == Path("/tmp/данные/dota-2-skin-studio")
    assert paths.settings == Path("/tmp/настройки/dota-2-skin-studio/settings.json")


def test_windows_paths_use_user_profile_directories(tmp_path: Path) -> None:
    paths = app_paths(
        {"APPDATA": r"C:\Users\tester\Roaming", "LOCALAPPDATA": r"C:\Users\tester\Local"},
        system="nt",
        home=tmp_path,
    )
    assert str(paths.data_dir).startswith(r"C:\Users\tester\Local")
    assert str(paths.config_dir).startswith(r"C:\Users\tester\Roaming")


def test_relative_xdg_values_fall_back_to_user_home(tmp_path: Path) -> None:
    paths = app_paths(
        {
            "XDG_DATA_HOME": "relative-data",
            "XDG_CONFIG_HOME": "relative-config",
            "XDG_CACHE_HOME": "relative-cache",
        },
        system="posix",
        home=tmp_path,
    )
    assert paths.data_dir == tmp_path / ".local" / "share" / "dota-2-skin-studio"


def test_settings_round_trip_uses_utf8_and_atomic_file(tmp_path: Path) -> None:
    path = tmp_path / "настройки" / "settings.json"
    expected = Settings(language="ru", steam_path="/home/тест/Steam", hotkey="Ctrl+Alt+K")
    save_settings(path, expected)
    assert load_settings(path) == expected
    assert "тест" in path.read_text(encoding="utf-8")
    assert list(path.parent.iterdir()) == [path]


@pytest.mark.parametrize(
    "contents",
    [
        "{broken",
        '{"version": 9, "language": "en"}',
        '{"version": 1, "language": "xx"}',
        '{"version": 1, "hotkey": "O"}',
    ],
)
def test_invalid_settings_are_rejected(tmp_path: Path, contents: str) -> None:
    path = tmp_path / "settings.json"
    path.write_text(contents, encoding="utf-8")
    with pytest.raises(ValueError):
        load_settings(path)
