# TaskFlow

TaskFlow is a private-chat Telegram task bot backed by MySQL. It uses Python's
standard library for Telegram long polling and `mysql-connector-python` for
database access.

## Requirements

- Windows
- Python 3.10 or newer
- MySQL 8.0.16 or newer
- A Telegram bot token from BotFather

## Configure and run

From PowerShell in this project folder:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create the schema with a MySQL account that has permission to create the
database and tables:

```powershell
cmd /c "mysql -u root -p < sql\schema.sql"
```

Create a dedicated database account and grant it access to the `taskflow`
database. Do not use the MySQL root account for the running bot.

Copy `.env.example` to `.env`, set your bot token and MySQL password there, and
keep `.env` private. TaskFlow loads `.env` using the standard library; variables
already set in the process environment take precedence.

```powershell
$env:TELEGRAM_BOT_TOKEN = "your-token"
$env:MYSQL_HOST = "127.0.0.1"
$env:MYSQL_PORT = "3306"
$env:MYSQL_DATABASE = "taskflow"
$env:MYSQL_USER = "taskflow_user"
$env:MYSQL_PASSWORD = "your-password"
python -m taskflow
```

The bot accepts commands in private chats. Use `/help` in Telegram for command
syntax. For `/add`, fields are separated with `|`; title is required and the
other fields can be left blank. A missing due date can be entered as `-`.

## Commands

- `/add <title> | <description> | <priority> | <YYYY-MM-DD or ->`
- `/tasks [page]`, `/pending [page]`, `/completed [page]`, `/overdue [page]`
- `/view <task_id>`
- `/update <task_id> <title|description|priority|due_date|status> <value>`
- `/done <task_id>`
- Use `/update <task_id> status pending` to reopen a completed task.
- `/delete <task_id>` followed by `/confirm_delete <task_id>`
- `/stats`, `/help`

Task updates, completion, and deletion are scoped to the Telegram sender's ID.
Deletion confirmation is per user and expires after 60 seconds. Pending
confirmation state is intentionally in memory; task data itself persists in
MySQL.

## Tests

Run the unit tests without a live Telegram bot or MySQL server:

```powershell
python -m unittest discover -v
```
