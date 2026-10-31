"""Add a generic cosmetic catalog and profile assignments."""

import sqlite3
import unicodedata

SAMPLE_ITEMS = (
    ("sample-hero-item", "Example hero cosmetic", "hero_item", "sample-axe", "set", "sample"),
    ("sample-courier", "Example courier", "courier", None, None, "sample"),
    ("sample-ward", "Example ward", "ward", None, None, "sample"),
    ("sample-weather", "Example weather effect", "weather", None, None, "sample"),
    ("sample-terrain", "Example terrain", "terrain", None, None, "sample"),
    ("sample-music", "Example music pack", "music", None, None, "sample"),
    ("sample-announcer", "Example announcer", "announcer", None, None, "sample"),
    ("sample-hud", "Example HUD theme", "hud", None, None, "sample"),
    ("sample-loading-screen", "Example loading screen", "loading_screen", None, None, "sample"),
    ("sample-taunt", "Example taunt", "taunt", None, None, "sample"),
    ("sample-ability-effect", "Example ability effect", "ability_effect", None, None, "sample"),
)


def upgrade(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE cosmetic_items (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            search_key TEXT NOT NULL,
            category TEXT NOT NULL,
            hero_id TEXT,
            slot TEXT,
            source TEXT NOT NULL,
            license_status TEXT NOT NULL,
            is_sample INTEGER NOT NULL DEFAULT 0 CHECK (is_sample IN (0, 1))
        )"""
    )
    connection.execute("CREATE INDEX idx_cosmetic_items_category ON cosmetic_items(category, name)")
    connection.execute(
        """CREATE TABLE profile_items (
            profile_id INTEGER NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
            item_id TEXT NOT NULL REFERENCES cosmetic_items(id) ON DELETE CASCADE,
            PRIMARY KEY (profile_id, item_id)
        )"""
    )
    connection.execute("CREATE INDEX idx_profile_items_item ON profile_items(item_id)")
    connection.execute(
        """CREATE TABLE cosmetic_favorites (
            item_id TEXT PRIMARY KEY REFERENCES cosmetic_items(id) ON DELETE CASCADE
        )"""
    )
    connection.executemany(
        """INSERT INTO cosmetic_items
           (id, name, search_key, category, hero_id, slot, source, license_status, is_sample)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'not_applicable', 1)""",
        (
            (identifier, name, _search_key(name), category, hero_id, slot, source)
            for identifier, name, category, hero_id, slot, source in SAMPLE_ITEMS
        ),
    )


def _search_key(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()
