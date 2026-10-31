import pytest

from skin_studio.services.shortcut_format import portal_trigger, windows_hotkey


def test_portal_shortcut_uses_xdg_trigger_syntax() -> None:
    assert portal_trigger("Ctrl+Shift+O") == "<Control><Shift>O"
    assert portal_trigger("Alt+F8") == "<Alt>F8"


def test_windows_shortcut_returns_register_hotkey_values() -> None:
    modifiers, virtual_key = windows_hotkey("Ctrl+Shift+O")
    assert modifiers == 0x4000 | 0x0002 | 0x0004
    assert virtual_key == ord("O")
    assert windows_hotkey("Alt+F8")[1] == 0x77


@pytest.mark.parametrize("shortcut", ["O", "Ctrl+Shift", "Ctrl+Ctrl+O", "Ctrl+F25"])
def test_shortcut_converters_reject_invalid_chords(shortcut: str) -> None:
    with pytest.raises(ValueError):
        portal_trigger(shortcut)
