"""Persistence operations for Telegram users."""

from __future__ import annotations

from typing import Any

from taskflow.database import Database


class UserRepository:
    def __init__(self, database: Database) -> None:
        self._database = database

    def upsert_user(
        self, user_id: int, username: str | None, first_name: str
    ) -> dict[str, Any]:
        query = """
            INSERT INTO users (user_id, username, first_name)
            VALUES (%s, %s, %s)
            ON DUPLICATE KEY UPDATE
                username = %s,
                first_name = %s
        """
        with self._database.transaction() as cursor:
            cursor.execute(
                query,
                (user_id, username, first_name, username, first_name),
            )
            cursor.execute(
                """
                SELECT user_id, username, first_name, registered_at
                FROM users
                WHERE user_id = %s
                """,
                (user_id,),
            )
            user = cursor.fetchone()
            if user is None:
                raise RuntimeError("User registration could not be verified.")
            return user
