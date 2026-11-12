from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from taskflow.database import Database
from taskflow.repositories.tasks import TaskRepository
from taskflow.repositories.users import UserRepository


class TaskRepositoryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.cursor = MagicMock()
        self.database = MagicMock(spec=Database)
        self.database.transaction.return_value.__enter__.return_value = self.cursor
        self.repository = TaskRepository(self.database)

    def test_task_lookup_is_user_scoped_and_parameterized(self) -> None:
        self.repository.get_task(41, 9)
        query, parameters = self.cursor.execute.call_args.args
        self.assertIn("WHERE task_id = %s AND user_id = %s", query)
        self.assertEqual(parameters, (9, 41))

    def test_update_is_user_scoped_and_uses_fixed_column_names(self) -> None:
        self.cursor.rowcount = 1
        self.repository.update_task(41, 9, "title", "Updated")
        query, parameters = self.cursor.execute.call_args.args
        self.assertIn("WHERE task_id = %s AND user_id = %s", query)
        self.assertNotIn("status = 'pending'", query)
        self.assertEqual(parameters, ("Updated", 9, 41))
        self.assertNotIn("Updated", query)

    def test_reopening_clears_completion_timestamp_and_checks_owner(self) -> None:
        self.cursor.rowcount = 1
        self.repository.reopen_task(41, 9)
        query, parameters = self.cursor.execute.call_args.args
        self.assertIn("completed_at = NULL", query)
        self.assertIn("WHERE task_id = %s AND user_id = %s", query)
        self.assertEqual(parameters, (9, 41))


class UserRepositoryTests(unittest.TestCase):
    def test_upsert_returns_the_persisted_user_record(self) -> None:
        cursor = MagicMock()
        cursor.fetchone.return_value = {
            "user_id": 41,
            "username": "sample",
            "first_name": "Sam",
            "registered_at": None,
        }
        database = MagicMock(spec=Database)
        database.transaction.return_value.__enter__.return_value = cursor
        repository = UserRepository(database)

        user = repository.upsert_user(41, "sample", "Sam")

        self.assertEqual(user["user_id"], 41)
        self.assertEqual(cursor.execute.call_count, 2)
        self.assertIn("ON DUPLICATE KEY UPDATE", cursor.execute.call_args_list[0].args[0])


if __name__ == "__main__":
    unittest.main()
