"""Input validation shared by command handlers and task services."""

from __future__ import annotations

from datetime import date

MAX_TASK_PAGE = 10_000


class ValidationError(ValueError):
    """Raised when a user-provided value is invalid."""


def validate_title(value: str) -> str:
    title = value.strip()
    if not title:
        raise ValidationError("A task title is required.")
    if len(title) > 200:
        raise ValidationError("Task titles must be 200 characters or fewer.")
    return title


def validate_description(value: str) -> str:
    description = value.strip()
    if len(description) > 4000:
        raise ValidationError("Descriptions must be 4,000 characters or fewer.")
    return description


def validate_priority(value: str) -> str:
    priority = value.strip().lower()
    if priority not in {"low", "medium", "high"}:
        raise ValidationError("Priority must be low, medium, or high.")
    return priority


def parse_due_date(value: str) -> date | None:
    normalized = value.strip().lower()
    if normalized in {"", "none", "-"}:
        return None
    try:
        parsed = date.fromisoformat(normalized)
    except ValueError as exc:
        raise ValidationError("Due date must use YYYY-MM-DD, or 'none'.") from exc
    if parsed.isoformat() != normalized:
        raise ValidationError("Due date must use YYYY-MM-DD, or 'none'.")
    return parsed


def parse_task_id(value: str) -> int:
    if not value.isdecimal() or len(value) > 20:
        raise ValidationError("Task ID must be a positive whole number.")
    task_id = int(value)
    if not 1 <= task_id <= 18_446_744_073_709_551_615:
        raise ValidationError("Task ID must be a positive whole number.")
    return task_id


def parse_page(value: str | None) -> int:
    if value is None:
        return 1
    if not value.isdecimal() or len(value) > 5:
        raise ValidationError("Page must be a positive whole number.")
    page = int(value)
    if not 1 <= page <= MAX_TASK_PAGE:
        raise ValidationError(f"Page must be between 1 and {MAX_TASK_PAGE}.")
    return page
