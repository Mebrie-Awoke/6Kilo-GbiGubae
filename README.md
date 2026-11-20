# 6Kilo GbiGubae

A Telegram community bot for member registration, administrator management, and scheduled text or media announcements.

## Architecture

- **Render web service:** receives Telegram updates through a verified webhook.
- **PostgreSQL:** stores users, schedules, Telegram update inbox entries, conversation state, and per-recipient broadcast delivery status.
- **GitHub Actions:** runs the scheduled-broadcast worker every five minutes, independently of Render uptime.

The Render service can sleep on the free plan. The first webhook after inactivity may be delayed by a cold start, but the webhook update is persisted before Telegram receives an acknowledgement. Pending updates and broadcast deliveries can resume after a restart.

## Required configuration

### Render environment variables

Set these in the Render service:

- `BOT_TOKEN` — Telegram bot token
- `SUPER_ADMIN_ID` — Telegram numeric ID of the super administrator
- `DATABASE_URL` — PostgreSQL connection string
- `WEBHOOK_SECRET` — random secret containing only letters, numbers, underscores, and hyphens

Render provides `RENDER_EXTERNAL_URL` automatically. If deploying elsewhere, set `WEBHOOK_BASE_URL` to the public HTTPS base URL.

### GitHub Actions secrets

In GitHub, open **Settings → Secrets and variables → Actions** and add:

- `BOT_TOKEN`
- `DATABASE_URL`
- `SUPER_ADMIN_ID`

The scheduled worker uses these secrets to connect directly to PostgreSQL and Telegram. Use a publicly reachable PostgreSQL connection URL for the GitHub Actions secret (not a Render-only internal hostname); configure your database provider's network access rules if it restricts external connections. Do not commit tokens or database URLs to the repository.

Generate a webhook secret locally with:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Paste the generated value into Render's `WEBHOOK_SECRET` environment variable.

## Deploy to Render

1. Back up the production PostgreSQL database.
2. Add all required Render environment variables.
3. From a trusted machine with the updated repository and production database URL configured, inspect the current Alembic revision and run `python -m alembic upgrade head` only after confirming that the existing database matches the repository's migration history.
4. Confirm the migration completes successfully. Do not continue if the database has no matching Alembic history or reports schema conflicts; reconcile the database first.
5. Manually deploy the Render service after the migration succeeds.
6. Confirm `/health/ready` reports that PostgreSQL is connected and the Telegram webhook is configured successfully in the Render logs.

The Render blueprint has automatic deployment disabled so releases can be deliberate. Enable it only after you are comfortable with the migration and release process.

## Scheduled broadcasts

The GitHub Actions workflow at `.github/workflows/scheduled-broadcasts.yml` runs every five minutes and can also be started manually from the Actions tab.

It creates a durable run for each due schedule and stores one delivery record per recipient. Pending and stale in-progress deliveries are retried on later runs. A broadcast may therefore continue after Render sleeps or restarts.

GitHub-hosted scheduled workflows are not an exact-time guarantee; they can start later than the cron time. Telegram also does not provide an idempotency key for message sends, so a rare duplicate remains possible if the worker crashes after Telegram accepts a message but before PostgreSQL records it as sent.

## Local development

Requirements: Python 3.11+ and PostgreSQL.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Create a `.env` file with the Render environment variables, plus `WEBHOOK_BASE_URL` pointing to a public HTTPS tunnel for local webhook testing.

Apply migrations and start the application:

```powershell
python -m alembic upgrade head
python main.py
```

Run the scheduled worker manually:

```powershell
python -m services.run_scheduled_jobs
```

## Health checks

- `/` — process liveness
- `/health/ready` — PostgreSQL readiness
- `/telegram/webhook` — Telegram webhook receiver (POST only)

## Tests

```powershell
python -m unittest discover -s tests -v
```

GitHub Actions runs syntax checks and unit tests on pushes and pull requests to `main`.

## Database safety

Use Alembic migrations to evolve the schema. The `_init_db.py` helper applies migrations and does not drop existing tables. Back up the production database before applying schema changes.

## License

No license has been declared in this repository. Confirm the upstream project's license before redistribution.
