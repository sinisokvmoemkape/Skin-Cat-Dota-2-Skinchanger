from pathlib import Path

from skin_studio.storage.database import connect_database
from skin_studio.storage.repositories.cosmetics import CosmeticRepository
from skin_studio.storage.repositories.profiles import ProfileRepository


def test_catalog_category_search_favorites_and_profile_assignments(tmp_path: Path) -> None:
    connection = connect_database(tmp_path / "app.sqlite3")
    catalog = CosmeticRepository(connection)
    profiles = ProfileRepository(connection)
    try:
        all_items = catalog.list_items()
        assert len(all_items) == 11
        assert all(item.is_sample for item in all_items)
        assert catalog.list_items(category="courier")[0].identifier == "sample-courier"
        assert catalog.list_items(query="COURIER")[0].identifier == "sample-courier"
        assert catalog.list_items(hero_id="sample-axe", slot="set")[0].identifier == (
            "sample-hero-item"
        )
        assert catalog.list_hero_ids() == ("sample-axe",)
        assert catalog.list_slots() == ("set",)

        connection.execute(
            """INSERT INTO cosmetic_items
               (id, name, search_key, category, source, license_status, is_sample)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            ("test-lina", "Лина", "лина", "hero_item", "fixture", "unknown", 0),
        )
        assert [item.identifier for item in catalog.list_items(query="ЛИНА")] == ["test-lina"]

        profile = profiles.create("Локальный набор")
        assert catalog.assign_to_profile(profile.identifier, "sample-courier")
        assert not catalog.assign_to_profile(profile.identifier, "sample-courier")
        assert catalog.list_profile_items(profile.identifier)[0].identifier == "sample-courier"
        assert catalog.toggle_favorite("sample-courier")
        assert catalog.list_items(favorites_only=True)[0].identifier == "sample-courier"
        assert not catalog.toggle_favorite("sample-courier")
        assert catalog.list_items(favorites_only=True) == ()
        catalog.remove_from_profile(profile.identifier, "sample-courier")
        assert catalog.list_profile_items(profile.identifier) == ()
        assert catalog.add_to_local_selection("sample-weather")
        assert not catalog.add_to_local_selection("sample-weather")
        assert catalog.list_local_selection()[0].identifier == "sample-weather"
        assert catalog.remove_from_local_selection("sample-weather")
        assert catalog.list_local_selection() == ()
    finally:
        connection.close()


def test_deleting_profile_cascades_cosmetic_assignments(tmp_path: Path) -> None:
    connection = connect_database(tmp_path / "app.sqlite3")
    profiles = ProfileRepository(connection)
    cosmetics = CosmeticRepository(connection)
    try:
        profile = profiles.create("Cascade test")
        cosmetics.assign_to_profile(profile.identifier, "sample-ward")
        profiles.delete(profile.identifier)
        assert connection.execute("SELECT COUNT(*) FROM profile_items").fetchone()[0] == 0
    finally:
        connection.close()


def test_duplicate_profile_copies_local_assignments(tmp_path: Path) -> None:
    connection = connect_database(tmp_path / "app.sqlite3")
    profiles = ProfileRepository(connection)
    cosmetics = CosmeticRepository(connection)
    try:
        original = profiles.create("Original")
        cosmetics.assign_to_profile(original.identifier, "sample-weather")
        duplicate = profiles.duplicate(original.identifier, "Duplicate")
        assert duplicate.name == "Duplicate"
        assert cosmetics.list_profile_items(duplicate.identifier)[0].identifier == "sample-weather"
    finally:
        connection.close()


def test_create_profile_with_imported_items_is_atomic(tmp_path: Path) -> None:
    from skin_studio.domain.errors import InvalidProfileImportError

    connection = connect_database(tmp_path / "app.sqlite3")
    profiles = ProfileRepository(connection)
    try:
        imported = profiles.create_with_items("Imported", ("sample-courier",))
        assert imported.name == "Imported"
        assert connection.execute("SELECT COUNT(*) FROM profile_items").fetchone()[0] == 1
        try:
            profiles.create_with_items("Broken", ("missing-item",))
        except InvalidProfileImportError:
            pass
        else:
            raise AssertionError("unknown item reference should be rejected")
        assert [profile.name for profile in profiles.list_profiles()] == ["Imported"]
    finally:
        connection.close()
