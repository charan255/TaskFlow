from __future__ import annotations

import unittest
from typing import Any

from taskflow.repositories.users import UserRepository
from taskflow.services.tasks import TaskService
from taskflow.handlers import CommandHandler
from taskflow.telegram_api import TelegramClient


class FakeClient(TelegramClient):
    def __init__(self) -> None:
        self.messages: list[tuple[int, str]] = []

    def send_message(self, chat_id: int, text: str) -> None:
        self.messages.append((chat_id, text))


class FakeUsers(UserRepository):
    def __init__(self) -> None:
        self.registered: list[tuple[int, str | None, str]] = []

    def upsert_user(
        self, user_id: int, username: str | None, first_name: str
    ) -> dict[str, Any]:
        self.registered.append((user_id, username, first_name))
        return {
            "user_id": user_id,
            "username": username,
            "first_name": first_name,
        }


class FakeTasks(TaskService):
    UPDATE_FIELDS = {"title", "description", "priority", "due_date", "status"}

    def __init__(self) -> None:
        self.created: list[tuple[Any, ...]] = []
        self.deleted: list[tuple[int, int]] = []

    def create_task(self, *args: Any) -> int:
        self.created.append(args)
        return 12

    def get_task(self, user_id: int, task_id: int) -> dict[str, Any]:
        return {"task_id": task_id, "title": "Plan"}

    def delete_task(self, user_id: int, task_id: int) -> None:
        self.deleted.append((user_id, task_id))


class CommandHandlerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.client = FakeClient()
        self.users = FakeUsers()
        self.tasks = FakeTasks()
        self.handler = CommandHandler(self.client, self.users, self.tasks)

    def update(self, user_id: int, text: str) -> dict[str, Any]:
        return {
            "message": {
                "chat": {"id": user_id, "type": "private"},
                "from": {
                    "id": user_id,
                    "username": "sample",
                    "first_name": "Sam",
                },
                "text": text,
            }
        }

    def test_add_registers_sender_and_parses_fields(self) -> None:
        self.handler.handle_update(
            self.update(31, "/add Write report | Draft | HIGH | 2026-12-01")
        )
        self.assertEqual(self.users.registered, [(31, "sample", "Sam")])
        self.assertEqual(
            self.tasks.created,
            [(31, "Write report", "Draft", "HIGH", "2026-12-01")],
        )
        self.assertIn("Task #12 created", self.client.messages[-1][1])

    def test_delete_requires_same_user_confirmation(self) -> None:
        self.handler.handle_update(self.update(31, "/delete 12"))
        self.handler.handle_update(self.update(32, "/confirm_delete 12"))
        self.assertEqual(self.tasks.deleted, [])
        self.assertIn("expired", self.client.messages[-1][1])

        self.handler.handle_update(self.update(31, "/confirm_delete 12"))
        self.assertEqual(self.tasks.deleted, [(31, 12)])

    def test_group_messages_are_ignored(self) -> None:
        update = self.update(31, "/start")
        update["message"]["chat"]["type"] = "group"
        self.handler.handle_update(update)
        self.assertEqual(self.users.registered, [])
        self.assertEqual(self.client.messages, [])


if __name__ == "__main__":
    unittest.main()
