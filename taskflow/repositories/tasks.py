"""Ownership-scoped persistence operations for tasks."""

from __future__ import annotations

from datetime import date
from typing import Any

from taskflow.database import Database


class TaskRepository:
    _UPDATE_COLUMNS = {
        "title": "title",
        "description": "description",
        "priority": "priority",
        "due_date": "due_date",
    }

    def __init__(self, database: Database) -> None:
        self._database = database

    def create_task(
        self,
        user_id: int,
        title: str,
        description: str,
        priority: str,
        due_date: date | None,
    ) -> int:
        query = """
            INSERT INTO tasks (user_id, title, description, priority, due_date)
            VALUES (%s, %s, %s, %s, %s)
        """
        with self._database.transaction() as cursor:
            cursor.execute(
                query, (user_id, title, description, priority, due_date)
            )
            return int(cursor.lastrowid)

    def get_task(self, user_id: int, task_id: int) -> dict[str, Any] | None:
        query = """
            SELECT task_id, user_id, title, description, priority, due_date,
                   status, created_at, updated_at, completed_at
            FROM tasks
            WHERE task_id = %s AND user_id = %s
        """
        with self._database.transaction() as cursor:
            cursor.execute(query, (task_id, user_id))
            return cursor.fetchone()

    def list_tasks(
        self,
        user_id: int,
        *,
        status: str | None,
        overdue_only: bool,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        conditions = ["user_id = %s"]
        parameters: list[Any] = [user_id]
        if status is not None:
            conditions.append("status = %s")
            parameters.append(status)
        if overdue_only:
            conditions.extend(["status = 'pending'", "due_date < CURDATE()"])

        query = f"""
            SELECT task_id, title, description, priority, due_date, status,
                   created_at, completed_at
            FROM tasks
            WHERE {" AND ".join(conditions)}
            ORDER BY
                CASE WHEN status = 'pending' THEN 0 ELSE 1 END,
                due_date IS NULL,
                due_date,
                task_id
            LIMIT %s OFFSET %s
        """
        parameters.extend((limit, offset))
        with self._database.transaction() as cursor:
            cursor.execute(query, tuple(parameters))
            return list(cursor.fetchall())

    def update_task(
        self, user_id: int, task_id: int, field: str, value: Any
    ) -> bool:
        column = self._UPDATE_COLUMNS[field]
        query = (
            f"UPDATE tasks SET {column} = %s "
            "WHERE task_id = %s AND user_id = %s"
        )
        with self._database.transaction() as cursor:
            cursor.execute(query, (value, task_id, user_id))
            return cursor.rowcount > 0

    def complete_task(self, user_id: int, task_id: int) -> bool:
        query = """
            UPDATE tasks
            SET status = 'completed', completed_at = CURRENT_TIMESTAMP
            WHERE task_id = %s AND user_id = %s AND status = 'pending'
        """
        with self._database.transaction() as cursor:
            cursor.execute(query, (task_id, user_id))
            return cursor.rowcount > 0

    def reopen_task(self, user_id: int, task_id: int) -> bool:
        query = """
            UPDATE tasks
            SET status = 'pending', completed_at = NULL
            WHERE task_id = %s AND user_id = %s AND status = 'completed'
        """
        with self._database.transaction() as cursor:
            cursor.execute(query, (task_id, user_id))
            return cursor.rowcount > 0

    def delete_task(self, user_id: int, task_id: int) -> bool:
        query = "DELETE FROM tasks WHERE task_id = %s AND user_id = %s"
        with self._database.transaction() as cursor:
            cursor.execute(query, (task_id, user_id))
            return cursor.rowcount > 0

    def get_statistics(self, user_id: int) -> dict[str, int]:
        query = """
            SELECT
                COUNT(*) AS total,
                COALESCE(SUM(status = 'pending'), 0) AS pending,
                COALESCE(SUM(status = 'completed'), 0) AS completed,
                COALESCE(SUM(
                    status = 'pending' AND due_date < CURDATE()
                ), 0) AS overdue,
                COALESCE(SUM(
                    status = 'pending' AND priority = 'high'
                ), 0) AS high_priority_pending
            FROM tasks
            WHERE user_id = %s
        """
        with self._database.transaction() as cursor:
            cursor.execute(query, (user_id,))
            result = cursor.fetchone()
            if result is None:
                raise RuntimeError("Task statistics could not be retrieved.")
            return {key: int(value) for key, value in result.items()}
