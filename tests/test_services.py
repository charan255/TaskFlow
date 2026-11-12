from __future__ import annotations

import unittest
from datetime import date
from typing import Any

from taskflow.services.tasks import (
    TaskAlreadyCompletedError,
    TaskNotFoundError,
    TaskService,
)
from taskflow.repositories.tasks import TaskRepository
from taskflow.validation import ValidationError


class FakeTaskRepository(TaskRepository):
    def __init__(self) -> None:
        self.tasks: dict[tuple[int, int], dict[str, Any]] = {}
        self.next_id = 1

    def create_task(
        self,
        user_id: int,
        title: str,
        description: str,
        priority: str,
        due_date: date | None,
    ) -> int:
        task_id = self.next_id
        self.next_id += 1
        self.tasks[(user_id, task_id)] = {
            "task_id": task_id,
            "user_id": user_id,
            "title": title,
            "description": description,
            "priority": priority,
            "due_date": due_date,
            "status": "pending",
        }
        return task_id

    def get_task(self, user_id: int, task_id: int) -> dict[str, Any] | None:
        return self.tasks.get((user_id, task_id))

    def list_tasks(
        self,
        user_id: int,
        *,
        status: str | None,
        overdue_only: bool,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        return []

    def update_task(
        self, user_id: int, task_id: int, field: str, value: Any
    ) -> bool:
        task = self.get_task(user_id, task_id)
        if task is None:
            return False
        task[field] = value
        return True

    def complete_task(self, user_id: int, task_id: int) -> bool:
        task = self.get_task(user_id, task_id)
        if task is None or task["status"] != "pending":
            return False
        task["status"] = "completed"
        return True

    def reopen_task(self, user_id: int, task_id: int) -> bool:
        task = self.get_task(user_id, task_id)
        if task is None or task["status"] != "completed":
            return False
        task["status"] = "pending"
        return True

    def delete_task(self, user_id: int, task_id: int) -> bool:
        return self.tasks.pop((user_id, task_id), None) is not None

    def get_statistics(self, user_id: int) -> dict[str, int]:
        return {
            "total": 0,
            "pending": 0,
            "completed": 0,
            "overdue": 0,
            "high_priority_pending": 0,
        }


class TaskServiceTests(unittest.TestCase):
    def setUp(self) -> None:
        self.repository = FakeTaskRepository()
        self.service = TaskService(self.repository)

    def test_create_validates_and_normalizes_task_fields(self) -> None:
        task_id = self.service.create_task(
            7, "  Review report  ", "  ", "HIGH", "2026-12-01"
        )
        task = self.service.get_task(7, task_id)
        self.assertEqual(task["title"], "Review report")
        self.assertEqual(task["priority"], "high")
        self.assertEqual(task["description"], "")
        self.assertEqual(str(task["due_date"]), "2026-12-01")

    def test_create_rejects_bad_priority_before_repository_write(self) -> None:
        with self.assertRaises(ValidationError):
            self.service.create_task(7, "Task", priority="urgent")
        self.assertEqual(self.repository.tasks, {})

    def test_task_lookup_and_updates_are_user_scoped(self) -> None:
        task_id = self.service.create_task(7, "Private task")
        with self.assertRaises(TaskNotFoundError):
            self.service.get_task(8, task_id)
        with self.assertRaises(TaskNotFoundError):
            self.service.update_task(8, task_id, "title", "Changed")
        self.assertEqual(self.service.get_task(7, task_id)["title"], "Private task")

    def test_completed_task_details_can_still_be_updated(self) -> None:
        task_id = self.service.create_task(7, "Finished")
        self.service.complete_task(7, task_id)
        updated = self.service.update_task(7, task_id, "title", "Renamed")
        self.assertEqual(updated["title"], "Renamed")
        self.assertEqual(updated["status"], "completed")

    def test_completion_cannot_be_repeated(self) -> None:
        task_id = self.service.create_task(7, "Finish task")
        self.service.complete_task(7, task_id)
        with self.assertRaises(TaskAlreadyCompletedError):
            self.service.complete_task(7, task_id)

    def test_status_update_can_reopen_completed_task(self) -> None:
        task_id = self.service.create_task(7, "Repeat task")
        self.service.complete_task(7, task_id)
        reopened = self.service.update_task(7, task_id, "status", "pending")
        self.assertEqual(reopened["status"], "pending")

    def test_empty_statistics_have_zero_completion_percentage(self) -> None:
        stats = self.service.get_statistics(7)
        self.assertEqual(stats["completion_percentage"], 0.0)


if __name__ == "__main__":
    unittest.main()
