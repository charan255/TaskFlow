"""Run the TaskFlow bot with ``python -m taskflow``."""

from __future__ import annotations

import logging

from taskflow.config import Config
from taskflow.database import Database
from taskflow.handlers import CommandHandler
from taskflow.polling import PollingBot
from taskflow.repositories.tasks import TaskRepository
from taskflow.repositories.users import UserRepository
from taskflow.services.tasks import TaskService
from taskflow.telegram_api import TelegramClient


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = Config.from_env()
    database = Database(config)
    client = TelegramClient(config.telegram_bot_token)
    handler = CommandHandler(
        client,
        UserRepository(database),
        TaskService(TaskRepository(database)),
    )
    logging.getLogger(__name__).info("TaskFlow is starting.")
    PollingBot(client, handler).run()


if __name__ == "__main__":
    main()
