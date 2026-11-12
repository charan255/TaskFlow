"""Telegram long-polling loop with retry handling."""

from __future__ import annotations

import logging
import time

from taskflow.handlers import CommandHandler, report_update_error
from taskflow.telegram_api import TelegramAPIError, TelegramClient

logger = logging.getLogger(__name__)


class PollingBot:
    def __init__(
        self,
        client: TelegramClient,
        handler: CommandHandler,
        poll_timeout: int = 30,
    ) -> None:
        self._client = client
        self._handler = handler
        self._poll_timeout = poll_timeout

    def run(self) -> None:
        offset: int | None = None
        retry_delay = 1
        while True:
            try:
                updates = self._client.get_updates(offset, self._poll_timeout)
                retry_delay = 1
            except TelegramAPIError as exc:
                if not exc.retryable:
                    logger.error("Telegram polling stopped: %s", exc)
                    raise
                logger.warning(
                    "Telegram polling failed (%s); retrying in %s seconds.",
                    exc,
                    retry_delay,
                )
                time.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)
                continue

            for update in updates:
                if not isinstance(update, dict):
                    continue
                try:
                    self._handler.handle_update(update)
                except Exception as exc:
                    report_update_error(self._client, update, exc)
                update_id = update.get("update_id")
                if isinstance(update_id, int):
                    offset = max(offset or 0, update_id + 1)
