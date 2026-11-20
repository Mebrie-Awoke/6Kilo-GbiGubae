# 6Kilo GbiGubae

A Telegram bot for community registration, administrator management, and scheduled text or media announcements.

## Requirements

- Python 3.11+
- PostgreSQL
- A Telegram bot token from [@BotFather](https://t.me/BotFather)

## Configuration

Create a `.env` file in the project root:

```env
TG_BOT_TOKEN=your_telegram_bot_token
SUPER_ADMIN_ID=your_telegram_user_id
DATABASE_URL=postgresql://user:password@host:5432/database
```

The application converts PostgreSQL URLs to the asyncpg driver automatically. Keep the `.env` file private and never commit credentials.

## Run locally

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m alembic upgrade head
python main.py
```

For Linux/macOS, activate the virtual environment with `source .venv/bin/activate`.

## Deployment

The repository includes a Render blueprint in `render.yaml`. Configure `TG_BOT_TOKEN` (or `BOT_TOKEN`), `SUPER_ADMIN_ID`, and `DATABASE_URL` as Render environment variables. Run database migrations with:

```bash
python -m alembic upgrade head
```

Health endpoints:

- `/` — process liveness
- `/health/ready` — PostgreSQL readiness
- `/ping` — simple ping

## Tests

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs Python compilation checks and the unit test suite on pushes and pull requests to `main`.

## Database safety

Use Alembic migrations to evolve the schema. The `_init_db.py` helper now applies migrations and no longer drops existing tables. Do not manually run destructive SQL against a production database.

## License

No license has been declared yet. Confirm the upstream project's license before redistributing or publishing modified copies.
