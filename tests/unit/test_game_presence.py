from types import SimpleNamespace

import psutil

from skin_studio.services.game_presence import GamePresenceService


def test_detects_dota_process_name_without_reading_other_fields() -> None:
    requested = {}

    def process_iter(**kwargs):
        requested.update(kwargs)
        return [SimpleNamespace(info={"name": "DOTA2.EXE"})]

    assert GamePresenceService(process_iter).is_dota_running()
    assert requested == {"attrs": ["name"], "ad_value": None}


def test_ignores_nonmatching_process_names() -> None:
    processes = [
        SimpleNamespace(info={"name": "dota2-helper"}),
        SimpleNamespace(info={"name": "steam"}),
        SimpleNamespace(info={"name": None}),
    ]
    assert not GamePresenceService(lambda **_kwargs: processes).is_dota_running()


def test_permission_and_process_race_errors_do_not_break_detection() -> None:
    class DeniedProcess:
        @property
        def info(self):
            raise psutil.AccessDenied(pid=4)

    def process_iter(**_kwargs):
        return [DeniedProcess(), SimpleNamespace(info={"name": "dota2"})]

    assert GamePresenceService(process_iter).is_dota_running()
    assert not GamePresenceService(
        lambda **_kwargs: (_ for _ in ()).throw(OSError("process list unavailable"))
    ).is_dota_running()
