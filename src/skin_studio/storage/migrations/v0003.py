"""Replace named cosmetic profiles with one local selection, preserving legacy rows."""

import sqlite3


def upgrade(connection: sqlite3.Connection) -> None:
    connection.execute(
        """CREATE TABLE local_selection_items (
            item_id TEXT PRIMARY KEY REFERENCES cosmetic_items(id) ON DELETE CASCADE
        )"""
    )
    connection.execute(
        """INSERT INTO local_selection_items(item_id)
           SELECT item_id FROM profile_items
           WHERE profile_id = (SELECT MIN(id) FROM profiles HAVING COUNT(*) = 1)"""
    )
