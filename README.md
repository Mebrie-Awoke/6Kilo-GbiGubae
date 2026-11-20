# 6Kilo GbiGubae

A lightweight Telegram bot for student registration, batch announcements and scheduled messages.

## Features

- Register members with only their Telegram ID, name and batch.
- View a profile and change a batch.
- Send an immediate announcement to one batch or all registered members.
- Schedule a text announcement for a batch or everyone.
- List and cancel pending scheduled messages.
- Protect administrator commands with a configured Telegram user ID.
- Store data in one JSON file with atomic writes.
- Resume pending scheduled deliveries after a process restart.

## Project structure

    .
    ├── bot/
    │   ├── config.py
    │   ├── handlers.py
    │   ├── scheduler.py
    │   ├── states.py
    │   └── storage.py
    ├── tests/
    ├── main.py
    ├── requirements.txt
    ├── render.yaml
    └── README.md

## Local setup

Requires Python 3.11 or newer.

    py -3.11 -m venv .venv
    .\.venv\Scripts\Activate.ps1
    pip install -r requirements.txt

Create a .env file:

    BOT_TOKEN=your_telegram_bot_token
    SUPER_ADMIN_ID=your_telegram_numeric_id
    DATA_FILE=data/data.json
    TIMEZONE=Africa/Addis_Ababa
    BATCHES=1st Year,2nd Year,3rd Year,4th Year,5th Year,6th Year

Run:

    python main.py

Without a public webhook URL, the bot uses Telegram long polling locally.

## Commands

### Members

- /start — Register or restart.
- /profile — View your name and batch.
- /edit_batch — Change your batch.
- /help — Show available commands.

### Administrator

Only the Telegram account configured in SUPER_ADMIN_ID can use these commands.

- /users — Count members by batch.
- /broadcast 1st Year | Your message — Send now to one batch.
- /broadcast all | Your message — Send now to everyone.
- /schedule 2026-11-22 09:00 | 1st Year | Your message — Schedule in the configured local timezone.
- /schedules — List pending schedules.
- /cancel_schedule 3 — Cancel schedule number 3.

Scheduled messages are text-only in this simplified version. Recurring schedules, media announcements, multiple administrators and advanced calendar editing were removed to keep the application small and easier to maintain.

## Deploy to Render

This repository includes a Render Blueprint using a persistent disk.

1. Push the repository to GitHub.
2. In Render, create a Blueprint deployment from this repository.
3. Set BOT_TOKEN to the token from BotFather.
4. Set SUPER_ADMIN_ID to the numeric Telegram ID of the administrator.
5. Generate a webhook secret locally:

       py -c "import secrets; print(secrets.token_urlsafe(32))"

6. Set the generated value as WEBHOOK_SECRET.
7. Deploy and wait for the health check to pass.

The Blueprint mounts a persistent disk at /var/data and stores the JSON file at /var/data/data.json. Keep one running instance only: JSON storage is designed for a single process and must not be shared by multiple bot instances.

A persistent disk and an always-running Render service are required for reliable scheduled delivery. If the service is stopped or unavailable at the scheduled time, the message will be sent when the service starts again. This can delay delivery; it cannot guarantee an exact send time while the service is offline.

## Vercel

Vercel is not a supported deployment target for this version. Its serverless execution and temporary filesystem are not appropriate for a bot that needs a continuously running scheduler and a persistent local JSON file. Use Render for this architecture.

## Data and reliability

- User records contain only Telegram ID (as the JSON object key), name and batch.
- Schedules contain the target batch, message, send time, creator ID and delivery progress.
- No PostgreSQL, SQLAlchemy, Alembic, migrations or external database are used.
- Writes use a temporary file followed by an atomic replace.
- If the JSON file is invalid, the bot stops rather than overwriting it. Restore a valid backup.
- Telegram does not provide an idempotency key for message sending. If the process stops after Telegram accepts a message but before its delivery is saved, that recipient may receive the message twice after restart.
- Back up /var/data/data.json periodically. A persistent disk is not a backup.

## Tests

    python -m unittest discover -s tests -v
