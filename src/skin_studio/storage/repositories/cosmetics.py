"""Read-only sample catalog queries and local profile assignments."""

from __future__ import annotations

import sqlite3
import unicodedata

from skin_studio.domain.models import CosmeticItem


class CosmeticRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def list_items(
        self,
        *,
        query: str = "",
        category: str | None = None,
        hero_id: str | None = None,
        slot: str | None = None,
        favorites_only: bool = False,
    ) -> tuple[CosmeticItem, ...]:
        normalized = _search_key(query.strip())
        clauses: list[str] = []
        parameters: list[str] = []
        if normalized:
            clauses.append("c.search_key LIKE ? ESCAPE '\\'")
            escaped = normalized.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
            parameters.append(f"%{escaped}%")
        if category:
            clauses.append("c.category = ?")
            parameters.append(category)
        if hero_id:
            clauses.append("c.hero_id = ?")
            parameters.append(hero_id)
        if slot:
            clauses.append("c.slot = ?")
            parameters.append(slot)
        if favorites_only:
            clauses.append("f.item_id IS NOT NULL")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._connection.execute(
            f"""SELECT c.id, c.name, c.category, c.hero_id, c.slot, c.source,
                       c.license_status, c.is_sample, f.item_id IS NOT NULL AS is_favorite
                FROM cosmetic_items AS c
                LEFT JOIN cosmetic_favorites AS f ON f.item_id = c.id
                {where}
                ORDER BY c.category, c.name COLLATE NOCASE""",
            parameters,
        ).fetchall()
        return tuple(_to_item(row) for row in rows)

    def list_hero_ids(self) -> tuple[str, ...]:
        rows = self._connection.execute(
            "SELECT DISTINCT hero_id FROM cosmetic_items WHERE hero_id IS NOT NULL ORDER BY hero_id"
        ).fetchall()
        return tuple(str(row[0]) for row in rows)

    def list_slots(self) -> tuple[str, ...]:
        rows = self._connection.execute(
            "SELECT DISTINCT slot FROM cosmetic_items WHERE slot IS NOT NULL ORDER BY slot"
        ).fetchall()
        return tuple(str(row[0]) for row in rows)

    def list_profile_items(self, profile_id: int) -> tuple[CosmeticItem, ...]:
        rows = self._connection.execute(
            """SELECT c.id, c.name, c.category, c.hero_id, c.slot, c.source,
                      c.license_status, c.is_sample,
                      f.item_id IS NOT NULL AS is_favorite
               FROM profile_items AS p
               JOIN cosmetic_items AS c ON c.id = p.item_id
               LEFT JOIN cosmetic_favorites AS f ON f.item_id = c.id
               WHERE p.profile_id = ?
               ORDER BY c.category, c.name COLLATE NOCASE""",
            (profile_id,),
        ).fetchall()
        return tuple(_to_item(row) for row in rows)

    def list_local_selection(self) -> tuple[CosmeticItem, ...]:
        rows = self._connection.execute(
            """SELECT c.id, c.name, c.category, c.hero_id, c.slot, c.source,
                      c.license_status, c.is_sample,
                      f.item_id IS NOT NULL AS is_favorite
               FROM local_selection_items AS s
               JOIN cosmetic_items AS c ON c.id = s.item_id
               LEFT JOIN cosmetic_favorites AS f ON f.item_id = c.id
               ORDER BY c.category, c.name COLLATE NOCASE"""
        ).fetchall()
        return tuple(_to_item(row) for row in rows)

    def toggle_favorite(self, item_id: str) -> bool:
        """Toggle favorite state and return the new state."""
        with self._connection:
            existing = self._connection.execute(
                "SELECT 1 FROM cosmetic_favorites WHERE item_id = ?", (item_id,)
            ).fetchone()
            if existing:
                self._connection.execute(
                    "DELETE FROM cosmetic_favorites WHERE item_id = ?", (item_id,)
                )
                return False
            self._connection.execute(
                "INSERT INTO cosmetic_favorites(item_id) VALUES (?)", (item_id,)
            )
        return True

    def assign_to_profile(self, profile_id: int, item_id: str) -> bool:
        with self._connection:
            cursor = self._connection.execute(
                "INSERT OR IGNORE INTO profile_items(profile_id, item_id) VALUES (?, ?)",
                (profile_id, item_id),
            )
        return cursor.rowcount > 0

    def remove_from_profile(self, profile_id: int, item_id: str) -> bool:
        with self._connection:
            cursor = self._connection.execute(
                "DELETE FROM profile_items WHERE profile_id = ? AND item_id = ?",
                (profile_id, item_id),
            )
        return cursor.rowcount > 0

    def add_to_local_selection(self, item_id: str) -> bool:
        with self._connection:
            cursor = self._connection.execute(
                "INSERT OR IGNORE INTO local_selection_items(item_id) VALUES (?)", (item_id,)
            )
        return cursor.rowcount > 0

    def remove_from_local_selection(self, item_id: str) -> bool:
        with self._connection:
            cursor = self._connection.execute(
                "DELETE FROM local_selection_items WHERE item_id = ?", (item_id,)
            )
        return cursor.rowcount > 0


def _search_key(value: str) -> str:
    return unicodedata.normalize("NFKC", value).casefold()


def _to_item(row: sqlite3.Row) -> CosmeticItem:
    return CosmeticItem(
        identifier=str(row["id"]),
        name=str(row["name"]),
        category=str(row["category"]),
        hero_id=str(row["hero_id"]) if row["hero_id"] is not None else None,
        slot=str(row["slot"]) if row["slot"] is not None else None,
        source=str(row["source"]),
        license_status=str(row["license_status"]),
        is_sample=bool(row["is_sample"]),
        is_favorite=bool(row["is_favorite"]),
    )
