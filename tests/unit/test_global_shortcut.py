from dbus_next import Message, MessageType, Variant

from skin_studio.services.global_shortcut import (
    PORTAL_PATH,
    SHORTCUT_ID,
    SHORTCUTS_IFACE,
    GlobalShortcutService,
)


def test_only_the_skin_cat_global_toggle_signal_is_forwarded(qapp) -> None:
    service = GlobalShortcutService()
    service._session_handle = "/org/freedesktop/portal/session/skin_cat"
    activations: list[bool] = []
    service.activated.connect(lambda: activations.append(True))

    def event(
        shortcut_id: str, session: str = "/org/freedesktop/portal/session/skin_cat"
    ) -> Message:
        return Message(
            message_type=MessageType.SIGNAL,
            path=PORTAL_PATH,
            interface=SHORTCUTS_IFACE,
            member="Activated",
            signature="osta{sv}",
            body=[session, shortcut_id, 1, {}],
        )

    assert service._handle_message(event(SHORTCUT_ID)) is False
    assert service._handle_message(event("some-other-action")) is False
    assert service._handle_message(event(SHORTCUT_ID, "/other/session")) is False
    assert activations == [True]


def test_portal_session_handle_is_unwrapped_from_dbus_variant() -> None:
    expected = "/org/freedesktop/portal/desktop/session/1_42/skin_cat"
    assert (
        GlobalShortcutService._session_path({"session_handle": Variant("o", expected)}) == expected
    )
