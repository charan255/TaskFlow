"""Minimal Telegram Bot API client using Python's standard library."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from typing import Any


class TelegramAPIError(RuntimeError):
    """Raised when Telegram rejects a request or cannot be reached."""

    def __init__(self, message: str, *, retryable: bool = True) -> None:
        super().__init__(message)
        self.retryable = retryable


class TelegramClient:
    MAX_MESSAGE_LENGTH = 4000

    def __init__(self, token: str, request_timeout: int = 40) -> None:
        self._base_url = f"https://api.telegram.org/bot{token}"
        self._request_timeout = request_timeout

    def _call(self, method: str, payload: dict[str, Any]) -> Any:
        request = urllib.request.Request(
            f"{self._base_url}/{method}",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request, timeout=self._request_timeout
            ) as response:
                body = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            raise TelegramAPIError(
                f"Telegram API {method} returned HTTP {exc.code}.",
                retryable=exc.code == 429 or exc.code >= 500,
            ) from None
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise TelegramAPIError(
                f"Telegram API {method} could not be reached "
                f"({type(exc).__name__})."
            ) from None
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TelegramAPIError(
                f"Telegram API {method} returned an invalid response."
            ) from None

        if not isinstance(body, dict) or not body.get("ok"):
            description = (
                body.get("description", "request failed")
                if isinstance(body, dict)
                else "invalid response"
            )
            error_code = body.get("error_code") if isinstance(body, dict) else None
            retryable = (
                not isinstance(error_code, int)
                or error_code == 429
                or error_code >= 500
            )
            raise TelegramAPIError(
                f"Telegram API {method} failed: {description}",
                retryable=retryable,
            )
        return body.get("result")

    def get_updates(self, offset: int | None, timeout: int = 30) -> list[dict]:
        payload: dict[str, Any] = {
            "timeout": timeout,
            "allowed_updates": ["message"],
        }
        if offset is not None:
            payload["offset"] = offset
        result = self._call("getUpdates", payload)
        if not isinstance(result, list):
            raise TelegramAPIError("Telegram API getUpdates returned invalid data.")
        return result

    def send_message(self, chat_id: int, text: str) -> None:
        remaining = text or " "
        while remaining:
            if self._utf16_length(remaining) <= self.MAX_MESSAGE_LENGTH:
                chunk, remaining = remaining, ""
            else:
                boundary = 0
                last_newline = -1
                for index, character in enumerate(remaining):
                    units = 2 if ord(character) > 0xFFFF else 1
                    if boundary + units > self.MAX_MESSAGE_LENGTH:
                        break
                    boundary += units
                    if character == "\n":
                        last_newline = index
                split_at = last_newline if last_newline > 0 else index
                if split_at <= 0:
                    split_at = index + 1
                chunk = remaining[:split_at]
                remaining = remaining[split_at:].lstrip("\n")
            self._call("sendMessage", {"chat_id": chat_id, "text": chunk})

    @staticmethod
    def _utf16_length(text: str) -> int:
        return len(text.encode("utf-16-le")) // 2
