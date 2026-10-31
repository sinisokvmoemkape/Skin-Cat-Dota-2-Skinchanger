"""Repository for user-created local profiles."""

import sqlite3
from datetime import datetime

from skin_studio.domain.errors import (
    DuplicateProfileError,
    InvalidProfileError,
    InvalidProfileImportError,
)
from skin_studio.domain.models import Profile

MAX_PROFILE_NAME_LENGTH = 80


class ProfileRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self._connection = connection

    def list_profiles(self) -> tuple[Profile, ...]:
        rows = self._connection.execute(
            "SELECT id, name, created_at FROM profiles ORDER BY name COLLATE NOCASE"
        ).fetchall()
        return tuple(
            Profile(int(row["id"]), str(row["name"]), datetime.fromisoformat(row["created_at"]))
            for row in rows
        )

    def create(self, name: str) -> Profile:
        normalized = _validate_name(name)
        try:
            with self._connection:
                cursor = self._connection.execute(
                    "INSERT INTO profiles(name, name_key) VALUES (?, ?)",
                    (normalized, normalized.casefold()),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateProfileError("A profile with this name already exists") from exc
        row = self._connection.execute(
            "SELECT id, name, created_at FROM profiles WHERE id = ?", (cursor.lastrowid,)
        ).fetchone()
        return Profile(int(row["id"]), str(row["name"]), datetime.fromisoformat(row["created_at"]))

    def create_with_items(self, name: str, item_ids: tuple[str, ...]) -> Profile:
        normalized = _validate_name(name)
        try:
            with self._connection:
                cursor = self._connection.execute(
                    "INSERT INTO profiles(name, name_key) VALUES (?, ?)",
                    (normalized, normalized.casefold()),
                )
                profile_id = int(cursor.lastrowid)
                self._connection.executemany(
                    "INSERT INTO profile_items(profile_id, item_id) VALUES (?, ?)",
                    ((profile_id, item_id) for item_id in item_ids),
                )
        except sqlite3.IntegrityError as exc:
            if "profiles.name_key" in str(exc):
                raise DuplicateProfileError("A profile with this name already exists") from exc
            raise InvalidProfileImportError("An imported catalog entry is unavailable") from exc
        return self._get(profile_id)

    def duplicate(self, identifier: int, name: str) -> Profile:
        normalized = _validate_name(name)
        try:
            with self._connection:
                source = self._connection.execute(
                    "SELECT id FROM profiles WHERE id = ?", (identifier,)
                ).fetchone()
                if source is None:
                    raise KeyError(identifier)
                cursor = self._connection.execute(
                    "INSERT INTO profiles(name, name_key) VALUES (?, ?)",
                    (normalized, normalized.casefold()),
                )
                new_id = int(cursor.lastrowid)
                self._connection.execute(
                    """INSERT INTO profile_items(profile_id, item_id)
                       SELECT ?, item_id FROM profile_items WHERE profile_id = ?""",
                    (new_id, identifier),
                )
        except sqlite3.IntegrityError as exc:
            raise DuplicateProfileError("A profile with this name already exists") from exc
        return self._get(new_id)

    def rename(self, identifier: int, name: str) -> None:
        normalized = _validate_name(name)
        try:
            with self._connection:
                cursor = self._connection.execute(
                    "UPDATE profiles SET name = ?, name_key = ? WHERE id = ?",
                    (normalized, normalized.casefold(), identifier),
                )
                if cursor.rowcount == 0:
                    raise KeyError(identifier)
        except sqlite3.IntegrityError as exc:
            raise DuplicateProfileError("A profile with this name already exists") from exc

    def delete(self, identifier: int) -> None:
        with self._connection:
            cursor = self._connection.execute("DELETE FROM profiles WHERE id = ?", (identifier,))
            if cursor.rowcount == 0:
                raise KeyError(identifier)

    def _get(self, identifier: int) -> Profile:
        row = self._connection.execute(
            "SELECT id, name, created_at FROM profiles WHERE id = ?", (identifier,)
        ).fetchone()
        if row is None:
            raise KeyError(identifier)
        return Profile(int(row["id"]), str(row["name"]), datetime.fromisoformat(row["created_at"]))


def _validate_name(name: str) -> str:
    normalized = name.strip()
    has_control_character = any(
        ord(character) < 32 or ord(character) == 127 for character in normalized
    )
    if not normalized or len(normalized) > MAX_PROFILE_NAME_LENGTH or has_control_character:
        raise InvalidProfileError("Profile name must contain between 1 and 80 characters")
    return normalized
