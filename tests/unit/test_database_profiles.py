from pathlib import Path

import pytest

from skin_studio.domain.errors import DuplicateProfileError, InvalidProfileError
from skin_studio.storage.database import connect_database, integrity_check, migrate
from skin_studio.storage.migrations.v0001 import upgrade as upgrade_v1
from skin_studio.storage.repositories.profiles import ProfileRepository


def test_fresh_database_migrates_and_enables_foreign_keys(tmp_path: Path) -> None:
    connection = connect_database(tmp_path / "app.sqlite3")
    try:
        assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
        assert connection.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        assert integrity_check(connection)
    finally:
        connection.close()


def test_database_rejects_future_schema(tmp_path: Path) -> None:
    path = tmp_path / "app.sqlite3"
    connection = connect_database(path)
    connection.execute("PRAGMA user_version = 99")
    connection.close()
    with pytest.raises(RuntimeError, match="newer"):
        connect_database(path)


def test_v1_database_migrates_catalog_without_losing_profiles() -> None:
    import sqlite3

    connection = sqlite3.connect(":memory:")
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    upgrade_v1(connection)
    connection.execute("INSERT INTO profiles(name, name_key) VALUES ('Existing', 'existing')")
    connection.commit()
    connection.execute("PRAGMA user_version = 1")
    migrate(connection)
    assert connection.execute("PRAGMA user_version").fetchone()[0] == 3
    assert connection.execute("SELECT name FROM profiles").fetchone()[0] == "Existing"
    assert connection.execute("SELECT COUNT(*) FROM cosmetic_items").fetchone()[0] == 11
    connection.close()


def test_single_legacy_profile_is_copied_to_the_local_selection(tmp_path: Path) -> None:
    import sqlite3

    from skin_studio.storage.migrations.v0002 import upgrade as upgrade_v2

    path = tmp_path / "legacy.sqlite3"
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    upgrade_v1(connection)
    upgrade_v2(connection)
    connection.execute("INSERT INTO profiles(name, name_key) VALUES ('Old set', 'old set')")
    connection.execute(
        "INSERT INTO profile_items(profile_id, item_id) VALUES (1, 'sample-courier')"
    )
    connection.execute("PRAGMA user_version = 2")
    connection.commit()
    connection.close()

    migrated = connect_database(path)
    try:
        selected = migrated.execute("SELECT item_id FROM local_selection_items").fetchall()
        assert [row[0] for row in selected] == ["sample-courier"]
        assert migrated.execute("SELECT name FROM profiles").fetchone()[0] == "Old set"
        assert migrated.execute("SELECT COUNT(*) FROM profile_items").fetchone()[0] == 1
    finally:
        migrated.close()


def test_multiple_legacy_profiles_are_preserved_without_choosing_one(tmp_path: Path) -> None:
    import sqlite3

    from skin_studio.storage.migrations.v0002 import upgrade as upgrade_v2

    path = tmp_path / "legacy-multiple.sqlite3"
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    upgrade_v1(connection)
    upgrade_v2(connection)
    connection.executemany(
        "INSERT INTO profiles(name, name_key) VALUES (?, ?)",
        (("First", "first"), ("Second", "second")),
    )
    connection.execute(
        "INSERT INTO profile_items(profile_id, item_id) VALUES (1, 'sample-courier')"
    )
    connection.execute(
        "INSERT INTO profile_items(profile_id, item_id) VALUES (2, 'sample-weather')"
    )
    connection.execute("PRAGMA user_version = 2")
    connection.commit()
    connection.close()

    migrated = connect_database(path)
    try:
        assert migrated.execute("SELECT COUNT(*) FROM local_selection_items").fetchone()[0] == 0
        assert migrated.execute("SELECT COUNT(*) FROM profiles").fetchone()[0] == 2
        assert migrated.execute("SELECT COUNT(*) FROM profile_items").fetchone()[0] == 2
    finally:
        migrated.close()


def test_profile_crud_and_duplicate_validation(tmp_path: Path) -> None:
    connection = connect_database(tmp_path / "app.sqlite3")
    repository = ProfileRepository(connection)
    try:
        first = repository.create("Мой профиль")
        assert repository.list_profiles() == (first,)
        repository.rename(first.identifier, "Новый профиль")
        assert repository.list_profiles()[0].name == "Новый профиль"
        repository.create("Второй")
        with pytest.raises(DuplicateProfileError):
            repository.create("второй")
        repository.delete(first.identifier)
        assert [profile.name for profile in repository.list_profiles()] == ["Второй"]
    finally:
        connection.close()


@pytest.mark.parametrize("name", ["", "   ", "x" * 81, "line\nbreak"])
def test_invalid_profile_names_are_rejected(tmp_path: Path, name: str) -> None:
    connection = connect_database(tmp_path / "app.sqlite3")
    try:
        with pytest.raises(InvalidProfileError):
            ProfileRepository(connection).create(name)
    finally:
        connection.close()
