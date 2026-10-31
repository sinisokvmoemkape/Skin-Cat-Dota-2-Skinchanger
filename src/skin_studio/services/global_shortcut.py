"""User-approved global shortcut registration through the XDG desktop portal."""

from __future__ import annotations

import asyncio
import threading
import uuid

from dbus_next import Message, MessageType, Variant
from dbus_next.aio import MessageBus
from PySide6.QtCore import QObject, Signal

from skin_studio.services.shortcut_format import portal_trigger

PORTAL = "org.freedesktop.portal.Desktop"
PORTAL_PATH = "/org/freedesktop/portal/desktop"
SHORTCUTS_IFACE = "org.freedesktop.portal.GlobalShortcuts"
REQUEST_IFACE = "org.freedesktop.portal.Request"
SESSION_IFACE = "org.freedesktop.portal.Session"
SHORTCUT_ID = "toggle-overlay"


class GlobalShortcutService(QObject):
    """Registers a desktop-managed shortcut without installing a key hook."""

    activated = Signal()
    status_changed = Signal(str)

    def __init__(self, shortcut: str = "Ctrl+Shift+O") -> None:
        super().__init__()
        self._shortcut = shortcut
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._bus: MessageBus | None = None
        self._session_handle: str | None = None
        self._pending_requests: dict[str, asyncio.Future] = {}
        self._early_responses: dict[str, tuple[int, dict]] = {}
        self._ready = threading.Event()

    def start(self) -> None:
        if self._thread is not None:
            return
        self._thread = threading.Thread(
            target=self._thread_main, name="skin-cat-shortcuts", daemon=True
        )
        self._thread.start()

    def stop(self) -> None:
        if self._loop is not None:
            self._loop.call_soon_threadsafe(self._loop.stop)

    def configure(self) -> None:
        if self._loop is None or not self._ready.is_set():
            self.status_changed.emit("Global shortcut service is not ready yet.")
            return
        asyncio.run_coroutine_threadsafe(self._configure(), self._loop)

    def set_shortcut(self, shortcut: str) -> None:
        self._shortcut = shortcut
        if self._loop is None or not self._ready.is_set():
            self.status_changed.emit("Registering the global overlay shortcut.")
            return
        self.status_changed.emit("Registering the global overlay shortcut.")
        asyncio.run_coroutine_threadsafe(self._set_shortcut(shortcut), self._loop)

    def _thread_main(self) -> None:
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._bus = self._loop.run_until_complete(MessageBus().connect())
            self._bus.add_message_handler(self._handle_message)
            self._session_handle = self._loop.run_until_complete(
                self._create_binding(self._shortcut)
            )
            self.status_changed.emit("Global shortcut is ready.")
            self._ready.set()
            self._loop.run_forever()
        except Exception:
            self.status_changed.emit("Global shortcut is unavailable in this desktop session.")
        finally:
            self._ready.clear()
            if self._bus is not None:
                self._bus.disconnect()
            self._loop.close()

    async def _create_binding(self, shortcut: str) -> str:
        if self._bus is None:
            raise RuntimeError("D-Bus session is unavailable")
        create_options = {
            "handle_token": Variant("s", f"create_{uuid.uuid4().hex}"),
            "session_handle_token": Variant("s", f"skin_cat_{uuid.uuid4().hex}"),
        }
        create_reply = await self._bus.call(
            Message(
                destination=PORTAL,
                path=PORTAL_PATH,
                interface=SHORTCUTS_IFACE,
                member="CreateSession",
                signature="a{sv}",
                body=[create_options],
            )
        )
        if create_reply.message_type == MessageType.ERROR:
            raise RuntimeError(
                create_reply.body[0] if create_reply.body else "CreateSession failed"
            )
        response, results = await self._wait_for_response(str(create_reply.body[0]))
        if response != 0:
            raise RuntimeError("The desktop declined global shortcut registration")
        session_handle = self._session_path(results)

        bind_reply = await self._bus.call(
            Message(
                destination=PORTAL,
                path=PORTAL_PATH,
                interface=SHORTCUTS_IFACE,
                member="BindShortcuts",
                signature="oa(sa{sv})sa{sv}",
                body=[
                    session_handle,
                    [
                        (
                            SHORTCUT_ID,
                            {
                                "description": Variant("s", "Show or hide the Skin Cat overlay"),
                                "preferred_trigger": Variant("s", portal_trigger(shortcut)),
                            },
                        )
                    ],
                    "",
                    {"handle_token": Variant("s", f"bind_{uuid.uuid4().hex}")},
                ],
            )
        )
        if bind_reply.message_type == MessageType.ERROR:
            raise RuntimeError(bind_reply.body[0] if bind_reply.body else "BindShortcuts failed")
        response, _ = await self._wait_for_response(str(bind_reply.body[0]))
        if response != 0:
            raise RuntimeError("The desktop declined global shortcut registration")
        return session_handle

    async def _wait_for_response(self, request_path: str) -> tuple[int, dict]:
        if self._bus is None or self._loop is None:
            raise RuntimeError("D-Bus session is unavailable")
        if request_path in self._early_responses:
            return self._early_responses.pop(request_path)
        future = self._loop.create_future()
        self._pending_requests[request_path] = future
        try:
            return await asyncio.wait_for(future, timeout=120)
        finally:
            self._pending_requests.pop(request_path, None)

    @staticmethod
    def _session_path(results: dict) -> str:
        handle = results["session_handle"]
        return str(handle.value if isinstance(handle, Variant) else handle)

    def _handle_message(self, message: Message) -> bool:
        if message.message_type != MessageType.SIGNAL:
            return False
        if message.interface == REQUEST_IFACE and message.member == "Response":
            future = self._pending_requests.get(message.path or "")
            result = (message.body[0], message.body[1])
            if future is not None and not future.done():
                future.set_result(result)
            else:
                self._early_responses[message.path or ""] = result
            return False
        if (
            message.interface == SHORTCUTS_IFACE
            and message.member == "Activated"
            and self._session_handle is not None
            and message.body[0] == self._session_handle
            and message.body[1] == SHORTCUT_ID
        ):
            self.activated.emit()
        return False

    async def _set_shortcut(self, shortcut: str) -> None:
        old_session = self._session_handle
        try:
            new_session = await self._create_binding(shortcut)
        except Exception:
            self.status_changed.emit("Could not register the selected global shortcut.")
            return
        self._session_handle = new_session
        if old_session is not None and self._bus is not None:
            try:
                await self._bus.call(
                    Message(
                        destination=PORTAL,
                        path=old_session,
                        interface=SESSION_IFACE,
                        member="Close",
                        signature="a{sv}",
                        body=[{}],
                    )
                )
            except Exception:
                pass
        self.status_changed.emit("Global shortcut is ready.")

    async def _configure(self) -> None:
        if self._bus is None or self._session_handle is None:
            self.status_changed.emit("Global shortcut registration is not active.")
            return
        options = {"handle_token": Variant("s", f"configure_{uuid.uuid4().hex}")}
        reply = await self._bus.call(
            Message(
                destination=PORTAL,
                path=PORTAL_PATH,
                interface=SHORTCUTS_IFACE,
                member="ConfigureShortcuts",
                signature="osa{sv}",
                body=[self._session_handle, "", options],
            )
        )
        if reply.message_type == MessageType.ERROR:
            self.status_changed.emit("Could not open shortcut settings in the desktop portal.")
        else:
            self.status_changed.emit("Shortcut settings opened in the desktop portal.")
