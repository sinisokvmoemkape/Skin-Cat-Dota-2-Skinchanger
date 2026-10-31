"""Windows global hotkeys using RegisterHotKey and Qt's native message filter."""

from __future__ import annotations

import ctypes
from ctypes import wintypes

from PySide6.QtCore import QAbstractNativeEventFilter, QObject, Signal
from PySide6.QtWidgets import QApplication

from skin_studio.services.shortcut_format import windows_hotkey

WM_HOTKEY = 0x0312
HOTKEY_ID = 0x5343


class _Point(ctypes.Structure):
    _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]


class _Message(ctypes.Structure):
    _fields_ = [
        ("hwnd", wintypes.HWND),
        ("message", wintypes.UINT),
        ("wParam", wintypes.WPARAM),
        ("lParam", wintypes.LPARAM),
        ("time", wintypes.DWORD),
        ("pt", _Point),
    ]


class WindowsGlobalShortcutService(QObject, QAbstractNativeEventFilter):
    """Registers one system-wide shortcut without a keyboard polling hook."""

    activated = Signal()
    status_changed = Signal(str)

    def __init__(self, shortcut: str = "Ctrl+Shift+O") -> None:
        QObject.__init__(self)
        QAbstractNativeEventFilter.__init__(self)
        self._shortcut = shortcut
        self._registered = False
        self._application: QApplication | None = None

    def start(self) -> None:
        self._application = QApplication.instance()
        if self._application is None:
            self.status_changed.emit("Global shortcut is unavailable in this desktop session.")
            return
        self._application.installNativeEventFilter(self)
        self._register(self._shortcut)

    def stop(self) -> None:
        if self._registered:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
            self._registered = False
        if self._application is not None:
            self._application.removeNativeEventFilter(self)

    def configure(self) -> None:
        self.status_changed.emit("Change the shortcut below and apply it.")

    def set_shortcut(self, shortcut: str) -> None:
        previous = self._shortcut
        if self._registered:
            ctypes.windll.user32.UnregisterHotKey(None, HOTKEY_ID)
            self._registered = False
        if self._register(shortcut):
            self._shortcut = shortcut
            return
        self._register(previous)
        self.status_changed.emit("Could not register the selected global shortcut.")

    def _register(self, shortcut: str) -> bool:
        try:
            modifiers, virtual_key = windows_hotkey(shortcut)
            success = bool(
                ctypes.windll.user32.RegisterHotKey(None, HOTKEY_ID, modifiers, virtual_key)
            )
        except (AttributeError, OSError, ValueError):
            success = False
        self._registered = success
        if success:
            self.status_changed.emit("Global shortcut is ready.")
        else:
            self.status_changed.emit("Could not register the selected global shortcut.")
        return success

    def nativeEventFilter(self, event_type, message):  # noqa: N802
        if event_type not in (b"windows_generic_MSG", b"windows_dispatcher_MSG"):
            return False, 0
        try:
            native_message = ctypes.cast(int(message), ctypes.POINTER(_Message)).contents
        except (TypeError, ValueError):
            return False, 0
        if native_message.message == WM_HOTKEY and native_message.wParam == HOTKEY_ID:
            self.activated.emit()
            return True, 0
        return False, 0
