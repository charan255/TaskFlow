"""Telegram command parsing, dispatch, and response formatting."""

from __future__ import annotations

import logging
import time
from datetime import date, datetime
from typing import Any

from taskflow.repositories.users import UserRepository
from taskflow.services.tasks import (
    TaskAlreadyCompletedError,
    TaskNotFoundError,
    TaskService,
)
from taskflow.telegram_api import TelegramClient
from taskflow.validation import (
    ValidationError,
    parse_page,
    parse_task_id,
)

logger = logging.getLogger(__name__)

HELP_TEXT = """TaskFlow commands:
/add <title> | <description> | <low|medium|high> | <YYYY-MM-DD or ->
/tasks [page] - all tasks
/pending [page] - pending tasks
/completed [page] - completed tasks
/overdue [page] - overdue pending tasks
/view <task_id> - view one task
/update <task_id> <title|description|priority|due_date|status> <value>
  Use 'none' to clear a due date; set status to pending or completed.
/done <task_id> - mark a task complete
/delete <task_id> - request deletion
/confirm_delete <task_id> - confirm deletion
/stats - task statistics
/help - show this help"""

COMMAND_USAGE = {
    "add": "Usage: /add <title> | <description> | <low|medium|high> | <YYYY-MM-DD or ->",
    "view": "Usage: /view <task_id>",
    "update": "Usage: /update <task_id> <title|description|priority|due_date|status> <value>",
    "done": "Usage: /done <task_id>",
    "delete": "Usage: /delete <task_id>",
    "confirm_delete": "Usage: /confirm_delete <task_id>",
}


def _format_date(value: Any) -> str:
    if value is None:
        return "none"
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


class CommandHandler:
    DELETE_CONFIRMATION_SECONDS = 60

    def __init__(
        self,
        client: TelegramClient,
        users: UserRepository,
        tasks: TaskService,
    ) -> None:
        self._client = client
        self._users = users
        self._tasks = tasks
        self._pending_deletions: dict[tuple[int, int], float] = {}

    def handle_update(self, update: dict[str, Any]) -> None:
        message = update.get("message")
        if not isinstance(message, dict):
            return
        chat = message.get("chat", {})
        sender = message.get("from", {})
        if not isinstance(chat, dict) or not isinstance(sender, dict):
            return
        if chat.get("type") != "private" or not isinstance(sender.get("id"), int):
            return

        user_id = sender["id"]
        chat_id = chat.get("id")
        if not isinstance(chat_id, int):
            return

        username = sender.get("username")
        first_name = sender.get("first_name") or "Telegram user"
        self._users.upsert_user(user_id, username, first_name)

        text = message.get("text")
        if not isinstance(text, str) or not text.strip():
            self._reply(chat_id, "Send a command to manage your tasks. Use /help.")
            return

        parts = text.strip().split(maxsplit=1)
        command = parts[0]
        arguments = parts[1] if len(parts) == 2 else ""
        if not command.startswith("/"):
            self._reply(chat_id, "Use a command to manage your tasks. Use /help.")
            return
        command = command[1:].split("@", 1)[0].lower()
        arguments = arguments.strip()

        try:
            self._dispatch(command, arguments, user_id, chat_id)
        except ValidationError as exc:
            self._reply(chat_id, str(exc))
        except TaskNotFoundError:
            self._reply(chat_id, "Task not found.")
        except TaskAlreadyCompletedError:
            self._reply(chat_id, "That task is already completed.")
        except ValueError as exc:
            self._reply(chat_id, str(exc))

    def _reply(self, chat_id: int, text: str) -> None:
        self._client.send_message(chat_id, text)

    def _dispatch(
        self, command: str, arguments: str, user_id: int, chat_id: int
    ) -> None:
        if command in {"start", "help"}:
            self._reply(chat_id, HELP_TEXT)
        elif command == "add":
            self._add(arguments, user_id, chat_id)
        elif command in {"tasks", "pending", "completed", "overdue"}:
            self._list(command, arguments, user_id, chat_id)
        elif command == "view":
            self._view(arguments, user_id, chat_id)
        elif command == "update":
            self._update(arguments, user_id, chat_id)
        elif command == "done":
            self._complete(arguments, user_id, chat_id)
        elif command == "delete":
            self._request_delete(arguments, user_id, chat_id)
        elif command == "confirm_delete":
            self._confirm_delete(arguments, user_id, chat_id)
        elif command == "stats":
            self._statistics(arguments, user_id, chat_id)
        else:
            self._reply(chat_id, "Unknown command. Use /help to see available commands.")

    def _add(self, arguments: str, user_id: int, chat_id: int) -> None:
        if not arguments:
            raise ValidationError(COMMAND_USAGE["add"])
        fields = [part.strip() for part in arguments.split("|")]
        if len(fields) > 4:
            raise ValidationError(COMMAND_USAGE["add"])
        title = fields[0]
        description = fields[1] if len(fields) > 1 else ""
        priority = fields[2] if len(fields) > 2 and fields[2] else "medium"
        due_date_value = fields[3] if len(fields) > 3 and fields[3] else "none"
        task_id = self._tasks.create_task(
            user_id, title, description, priority, due_date_value
        )
        self._reply(chat_id, f"Task #{task_id} created.")

    def _list(
        self, command: str, arguments: str, user_id: int, chat_id: int
    ) -> None:
        words = arguments.split()
        if len(words) > 1:
            raise ValidationError(f"Usage: /{command} [page]")
        page = parse_page(words[0] if words else None)
        status = {
            "pending": "pending",
            "completed": "completed",
        }.get(command)
        tasks = self._tasks.list_tasks(
            user_id,
            status=status,
            overdue_only=command == "overdue",
            page=page,
        )
        if not tasks:
            self._reply(chat_id, f"No {command} tasks on page {page}.")
            return

        lines = [f"{command.title()} tasks (page {page}):"]
        for task in tasks:
            description = task["description"] or ""
            if len(description) > 120:
                description = description[:117] + "..."
            line = (
                f"#{task['task_id']} [{task['status']}] {task['title']} "
                f"({task['priority']}, due {_format_date(task['due_date'])})"
            )
            if description:
                line += f"\n  {description}"
            lines.append(line)
        lines.append(f"Use /{command} {page + 1} for the next page.")
        self._reply(chat_id, "\n".join(lines))

    def _view(self, arguments: str, user_id: int, chat_id: int) -> None:
        words = arguments.split()
        if len(words) != 1:
            raise ValidationError(COMMAND_USAGE["view"])
        task = self._tasks.get_task(user_id, parse_task_id(words[0]))
        text = (
            f"Task #{task['task_id']}: {task['title']}\n"
            f"Status: {task['status']}\n"
            f"Priority: {task['priority']}\n"
            f"Due: {_format_date(task['due_date'])}\n"
            f"Created: {_format_date(task['created_at'])}\n"
            f"Description: {task['description'] or '(none)'}"
        )
        if task.get("completed_at") is not None:
            text += f"\nCompleted: {_format_date(task['completed_at'])}"
        self._reply(chat_id, text)

    def _update(self, arguments: str, user_id: int, chat_id: int) -> None:
        words = arguments.split(maxsplit=2)
        if len(words) != 3:
            raise ValidationError(COMMAND_USAGE["update"])
        task_id = parse_task_id(words[0])
        field = words[1].lower()
        if field not in TaskService.UPDATE_FIELDS:
            raise ValidationError(
                "Field must be title, description, priority, due_date, or status."
            )
        self._tasks.update_task(user_id, task_id, field, words[2])
        self._reply(chat_id, f"Task #{task_id} updated.")

    def _complete(self, arguments: str, user_id: int, chat_id: int) -> None:
        words = arguments.split()
        if len(words) != 1:
            raise ValidationError(COMMAND_USAGE["done"])
        task_id = parse_task_id(words[0])
        self._tasks.complete_task(user_id, task_id)
        self._reply(chat_id, f"Task #{task_id} marked completed.")

    def _request_delete(self, arguments: str, user_id: int, chat_id: int) -> None:
        words = arguments.split()
        if len(words) != 1:
            raise ValidationError(COMMAND_USAGE["delete"])
        task_id = parse_task_id(words[0])
        task = self._tasks.get_task(user_id, task_id)
        self._pending_deletions[(user_id, task_id)] = (
            time.monotonic() + self.DELETE_CONFIRMATION_SECONDS
        )
        self._reply(
            chat_id,
            f"Delete task #{task_id} ({task['title']})? "
            f"Confirm with /confirm_delete {task_id} within 60 seconds.",
        )

    def _confirm_delete(self, arguments: str, user_id: int, chat_id: int) -> None:
        words = arguments.split()
        if len(words) != 1:
            raise ValidationError(COMMAND_USAGE["confirm_delete"])
        task_id = parse_task_id(words[0])
        expires_at = self._pending_deletions.pop((user_id, task_id), None)
        if expires_at is None or time.monotonic() > expires_at:
            self._reply(chat_id, "Deletion confirmation expired. Use /delete again.")
            return
        self._tasks.delete_task(user_id, task_id)
        self._reply(chat_id, f"Task #{task_id} deleted.")

    def _statistics(self, arguments: str, user_id: int, chat_id: int) -> None:
        if arguments:
            raise ValidationError("Usage: /stats")
        stats = self._tasks.get_statistics(user_id)
        self._reply(
            chat_id,
            "Task statistics:\n"
            f"Total: {stats['total']}\n"
            f"Pending: {stats['pending']}\n"
            f"Completed: {stats['completed']}\n"
            f"Overdue: {stats['overdue']}\n"
            f"High-priority pending: {stats['high_priority_pending']}\n"
            f"Completion: {stats['completion_percentage']}%",
        )


def report_update_error(
    client: TelegramClient, update: dict[str, Any], error: Exception
) -> None:
    """Log an unhandled update failure and send a generic retry message."""
    logger.error(
        "Update processing failed: %s", type(error).__name__, exc_info=True
    )
    message = update.get("message", {})
    chat = message.get("chat", {}) if isinstance(message, dict) else {}
    chat_id = chat.get("id") if isinstance(chat, dict) else None
    if isinstance(chat_id, int) and chat.get("type") == "private":
        try:
            client.send_message(
                chat_id, "TaskFlow could not process that request. Please try again."
            )
        except Exception:
            logger.error("Could not send an update error message.")
