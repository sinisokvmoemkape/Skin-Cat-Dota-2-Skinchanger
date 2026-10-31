"""Portable conversion helpers for supported global shortcut key chords."""

from __future__ import annotations

from skin_studio.config import is_valid_hotkey

PORTAL_MODIFIERS = {
    "ctrl": "Control",
    "shift": "Shift",
    "alt": "Alt",
    "meta": "Super",
}

WIN_MODIFIERS = {"ctrl": 0x0002, "shift": 0x0004, "alt": 0x0001, "meta": 0x0008}


def portal_trigger(shortcut: str) -> str:
    if not is_valid_hotkey(shortcut):
        raise ValueError("Unsupported global shortcut")
    parts = shortcut.split("+")
    modifiers = "".join(f"<{PORTAL_MODIFIERS[part.casefold()]}>" for part in parts[:-1])
    return f"{modifiers}{parts[-1].upper()}"


def windows_hotkey(shortcut: str) -> tuple[int, int]:
    """Return RegisterHotKey modifier and virtual-key values."""
    if not is_valid_hotkey(shortcut):
        raise ValueError("Unsupported global shortcut")
    parts = shortcut.split("+")
    modifiers = 0x4000  # MOD_NOREPEAT
    for modifier in parts[:-1]:
        modifiers |= WIN_MODIFIERS[modifier.casefold()]
    key = parts[-1].upper()
    if len(key) == 1 and key.isascii() and key.isalnum():
        virtual_key = ord(key)
    else:
        virtual_key = 0x70 + int(key[1:]) - 1  # VK_F1 through VK_F24
    return modifiers, virtual_key
