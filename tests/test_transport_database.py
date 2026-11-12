from __future__ import annotations

import unittest
import urllib.error
import json
from unittest.mock import patch

from taskflow.database import Database
from taskflow.telegram_api import TelegramAPIError, TelegramClient


class FakeCursor:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeConnection:
    def __init__(self) -> None:
        self.cursor_instance = FakeCursor()
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self, *, dictionary: bool) -> FakeCursor:
        if not dictionary:
            raise AssertionError("Expected a dictionary cursor.")
        return self.cursor_instance

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True

    def close(self) -> None:
        self.closed = True


class FakePool:
    def __init__(self, connection: FakeConnection) -> None:
        self.connection = connection

    def get_connection(self) -> FakeConnection:
        return self.connection


class TransactionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = FakeConnection()
        self.database = object.__new__(Database)
        self.database._pool = FakePool(self.connection)

    def test_commits_and_releases_resources_on_success(self) -> None:
        with self.database.transaction() as cursor:
            self.assertIs(cursor, self.connection.cursor_instance)
        self.assertTrue(self.connection.committed)
        self.assertTrue(self.connection.cursor_instance.closed)
        self.assertTrue(self.connection.closed)

    def test_rolls_back_and_releases_resources_on_failure(self) -> None:
        with self.assertRaisesRegex(RuntimeError, "failed"):
            with self.database.transaction():
                raise RuntimeError("failed")
        self.assertTrue(self.connection.rolled_back)
        self.assertTrue(self.connection.cursor_instance.closed)
        self.assertTrue(self.connection.closed)


class TelegramClientTests(unittest.TestCase):
    def test_splits_long_messages_under_telegram_limit(self) -> None:
        client = TelegramClient("not-a-real-token")
        with patch.object(client, "_call") as api_call:
            client.send_message(5, "x" * 9000)
        lengths = [
            len(call.args[1]["text"]) for call in api_call.call_args_list
        ]
        self.assertEqual(lengths, [4000, 4000, 1000])

    def test_splits_messages_by_telegram_utf16_character_limit(self) -> None:
        client = TelegramClient("not-a-real-token")
        text = "😀" * 2500
        with patch.object(client, "_call") as api_call:
            client.send_message(5, text)
        chunks = [
            call.args[1]["text"] for call in api_call.call_args_list
        ]
        self.assertEqual("".join(chunks), text)
        self.assertTrue(
            all(client._utf16_length(chunk) <= 4000 for chunk in chunks)
        )

    def test_transport_error_does_not_expose_bot_token(self) -> None:
        client = TelegramClient("sensitive-token")
        with patch(
            "taskflow.telegram_api.urllib.request.urlopen",
            side_effect=urllib.error.URLError("connection failed"),
        ):
            with self.assertRaises(TelegramAPIError) as raised:
                client._call("getMe", {})
        self.assertNotIn("sensitive-token", str(raised.exception))

    def test_invalid_token_error_is_not_marked_retryable(self) -> None:
        class FakeResponse:
            def __enter__(self) -> FakeResponse:
                return self

            def __exit__(self, *args: object) -> None:
                return None

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "ok": False,
                        "error_code": 401,
                        "description": "Unauthorized",
                    }
                ).encode()

        client = TelegramClient("not-a-real-token")
        with patch(
            "taskflow.telegram_api.urllib.request.urlopen",
            return_value=FakeResponse(),
        ):
            with self.assertRaises(TelegramAPIError) as raised:
                client.get_updates(None)
        self.assertFalse(raised.exception.retryable)


if __name__ == "__main__":
    unittest.main()
