from __future__ import annotations

import unittest
import tempfile
from pathlib import Path

from taskflow.config import Config, load_dotenv
from taskflow.validation import (
    ValidationError,
    parse_due_date,
    parse_page,
    parse_task_id,
    validate_priority,
    validate_title,
)


class ConfigTests(unittest.TestCase):
    def test_reads_required_values_and_defaults(self) -> None:
        config = Config.from_env(
            {
                "TELEGRAM_BOT_TOKEN": "token",
                "MYSQL_HOST": "localhost",
                "MYSQL_DATABASE": "taskflow",
                "MYSQL_USER": "bot",
            }
        )
        self.assertEqual(config.mysql_port, 3306)
        self.assertEqual(config.mysql_pool_size, 5)
        self.assertEqual(config.mysql_password, "")

    def test_reports_missing_variables_without_revealing_values(self) -> None:
        with self.assertRaisesRegex(ValueError, "TELEGRAM_BOT_TOKEN"):
            Config.from_env({})

    def test_rejects_out_of_range_port_and_pool_size(self) -> None:
        values = {
            "TELEGRAM_BOT_TOKEN": "token",
            "MYSQL_HOST": "localhost",
            "MYSQL_DATABASE": "taskflow",
            "MYSQL_USER": "bot",
            "MYSQL_PORT": "70000",
        }
        with self.assertRaisesRegex(ValueError, "MYSQL_PORT"):
            Config.from_env(values)
        values["MYSQL_PORT"] = "3306"
        values["MYSQL_POOL_SIZE"] = "0"
        with self.assertRaisesRegex(ValueError, "MYSQL_POOL_SIZE"):
            Config.from_env(values)

    def test_loads_dotenv_without_overwriting_existing_environment(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "# local settings\nTELEGRAM_BOT_TOKEN='private-token'\n"
                "MYSQL_HOST=localhost\n",
                encoding="utf-8",
            )
            values = {"MYSQL_HOST": "db.internal"}
            load_dotenv(path, values)

        self.assertEqual(values["TELEGRAM_BOT_TOKEN"], "private-token")
        self.assertEqual(values["MYSQL_HOST"], "db.internal")


class ValidationTests(unittest.TestCase):
    def test_normalizes_values_and_dates(self) -> None:
        self.assertEqual(validate_title("  Write tests "), "Write tests")
        self.assertEqual(validate_priority(" HIGH "), "high")
        self.assertEqual(str(parse_due_date("2026-12-01")), "2026-12-01")
        self.assertIsNone(parse_due_date("none"))

    def test_rejects_invalid_values_and_ids(self) -> None:
        with self.assertRaises(ValidationError):
            validate_title("  ")
        with self.assertRaises(ValidationError):
            validate_priority("urgent")
        with self.assertRaises(ValidationError):
            parse_due_date("2026-02-30")
        with self.assertRaises(ValidationError):
            parse_task_id("0")
        with self.assertRaises(ValidationError):
            parse_task_id("18446744073709551616")
        with self.assertRaises(ValidationError):
            parse_task_id("1" * 100)
        with self.assertRaises(ValidationError):
            parse_page("1.5")
        with self.assertRaises(ValidationError):
            parse_page("9" * 100)


if __name__ == "__main__":
    unittest.main()
