"""MySQL connection pooling and transaction management."""

from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from mysql.connector.cursor import MySQLCursorDict
from mysql.connector.pooling import MySQLConnectionPool

from taskflow.config import Config


class Database:
    def __init__(self, config: Config) -> None:
        self._pool = MySQLConnectionPool(
            pool_name=config.mysql_pool_name,
            pool_size=config.mysql_pool_size,
            host=config.mysql_host,
            port=config.mysql_port,
            database=config.mysql_database,
            user=config.mysql_user,
            password=config.mysql_password,
            autocommit=False,
        )

    @contextmanager
    def transaction(self) -> Iterator[MySQLCursorDict]:
        connection = self._pool.get_connection()
        try:
            cursor = connection.cursor(dictionary=True)
            try:
                yield cursor
                connection.commit()
            except BaseException:
                connection.rollback()
                raise
            finally:
                cursor.close()
        finally:
            connection.close()
