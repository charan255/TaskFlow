"""Task business rules, independent of Telegram updates."""

from __future__ import annotations

from typing import Any

from taskflow.repositories.tasks import TaskRepository
from taskflow.validation import (
    parse_due_date,
    validate_description,
    validate_priority,
    validate_title,
)


class TaskNotFoundError(LookupError):
    """Raised when a task is missing or is not owned by the requesting user."""


class TaskAlreadyCompletedError(ValueError):
    """Raised when completion is requested for an already completed task."""


class TaskService:
    PAGE_SIZE = 8
    MAX_PAGE = 10_000
    UPDATE_FIELDS = {"title", "description", "priority", "due_date", "status"}

    def __init__(self, repository: TaskRepository) -> None:
        self._repository = repository

    def create_task(
        self,
        user_id: int,
        title: str,
        description: str = "",
        priority: str = "medium",
        due_date_value: str = "none",
    ) -> int:
        return self._repository.create_task(
            user_id,
            validate_title(title),
            validate_description(description),
            validate_priority(priority),
            parse_due_date(due_date_value),
        )

    def get_task(self, user_id: int, task_id: int) -> dict[str, Any]:
        task = self._repository.get_task(user_id, task_id)
        if task is None:
            raise TaskNotFoundError
        return task

    def list_tasks(
        self,
        user_id: int,
        *,
        status: str | None = None,
        overdue_only: bool = False,
        page: int = 1,
    ) -> list[dict[str, Any]]:
        if not 1 <= page <= self.MAX_PAGE:
            raise ValueError(
                f"Page must be between 1 and {self.MAX_PAGE}."
            )
        if status not in {None, "pending", "completed"}:
            raise ValueError("Unsupported task status.")
        return self._repository.list_tasks(
            user_id,
            status=status,
            overdue_only=overdue_only,
            limit=self.PAGE_SIZE,
            offset=(page - 1) * self.PAGE_SIZE,
        )

    def update_task(
        self, user_id: int, task_id: int, field: str, value: str
    ) -> dict[str, Any]:
        if field not in self.UPDATE_FIELDS:
            raise ValueError("Unsupported task field.")

        if field == "title":
            normalized: Any = validate_title(value)
        elif field == "description":
            normalized = validate_description(value)
        elif field == "priority":
            normalized = validate_priority(value)
        elif field == "status":
            normalized = value.strip().lower()
            if normalized not in {"pending", "completed"}:
                raise ValueError("Status must be pending or completed.")
            if normalized == "completed":
                self.complete_task(user_id, task_id)
                return self.get_task(user_id, task_id)
            self._repository.reopen_task(user_id, task_id)
            task = self._repository.get_task(user_id, task_id)
            if task is None:
                raise TaskNotFoundError
            return task
        else:
            normalized = parse_due_date(value)

        self._repository.update_task(user_id, task_id, field, normalized)
        task = self._repository.get_task(user_id, task_id)
        if task is None:
            raise TaskNotFoundError
        return task

    def complete_task(self, user_id: int, task_id: int) -> None:
        if self._repository.complete_task(user_id, task_id):
            return
        task = self._repository.get_task(user_id, task_id)
        if task is None:
            raise TaskNotFoundError
        raise TaskAlreadyCompletedError

    def delete_task(self, user_id: int, task_id: int) -> None:
        if not self._repository.delete_task(user_id, task_id):
            raise TaskNotFoundError

    def get_statistics(self, user_id: int) -> dict[str, int | float]:
        result: dict[str, int | float] = dict(
            self._repository.get_statistics(user_id)
        )
        total = result["total"]
        result["completion_percentage"] = (
            round(result["completed"] * 100 / total, 1) if total else 0.0
        )
        return result
