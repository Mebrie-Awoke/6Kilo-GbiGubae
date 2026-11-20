# 6Kilo GbiGubae

Amharic-first Telegram community bot with a FastAPI service and MongoDB Atlas storage.

## Features

- Member registration, profiles and batch updates.
- Guided announcements for all members or a selected batch.
- Scheduled announcements using Ethiopian calendar dates.
- Admin dashboard, member summaries and schedule management.
- MongoDB collections and indexes initialized automatically.

## Local setup

Python 3.11+

```bash
py -3.11 -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt
```

Create a `.env` file:

```env
BOT_TOKEN=your_bot_token
SUPER_ADMIN_ID=your_telegram_user_id
MONGODB_URI=your_mongodb_atlas_connection_string
MONGODB_DATABASE=gbigubae_bot
TIMEZONE=Africa/Addis_Ababa
```

Run:

```bash
python main.py
```

The API runs on port 8080 by default. Without a public webhook URL, the bot uses Telegram polling locally. On Render, set `WEBHOOK_SECRET`; Render's public URL is detected automatically.

## API

- `GET /` — service health.
- `GET /health/ready` — MongoDB readiness.
- `POST /telegram/webhook` — Telegram updates.
- `GET /docs` — interactive API documentation.

## MongoDB

At startup, the application connects to the configured database and creates the `users`, `schedules`, and `counters` collections and required indexes automatically. No manual database or collection creation is needed.

## Tests

```bash
python -m unittest discover -s tests -v
```
