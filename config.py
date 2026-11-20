"""Application configuration loaded from environment variables."""
import os

from dotenv import load_dotenv

from db.url import normalize_async_database_url

load_dotenv()

BOT_TOKEN = os.getenv("TG_BOT_TOKEN") or os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise RuntimeError("TG_BOT_TOKEN (or BOT_TOKEN) is required.")

_super_admin_id = os.getenv("SUPER_ADMIN_ID")
if not _super_admin_id:
    raise RuntimeError("SUPER_ADMIN_ID is required. Set it to the Telegram ID of the super admin.")

try:
    SUPER_ADMIN_ID = int(_super_admin_id) if _super_admin_id else None
except ValueError as exc:
    raise ValueError("SUPER_ADMIN_ID must be a valid Telegram user ID.") from exc

_raw_database_url = os.getenv("DATABASE_URL")
DATABASE_URL = (
    normalize_async_database_url(_raw_database_url)
    if _raw_database_url
    else None
)

WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET")
if not WEBHOOK_SECRET:
    raise RuntimeError("WEBHOOK_SECRET is required for Telegram webhook verification.")

WEBHOOK_BASE_URL = (
    os.getenv("WEBHOOK_BASE_URL") or os.getenv("RENDER_EXTERNAL_URL")
)
if not WEBHOOK_BASE_URL:
    raise RuntimeError(
        "WEBHOOK_BASE_URL or Render's RENDER_EXTERNAL_URL must be configured."
    )
WEBHOOK_BASE_URL = WEBHOOK_BASE_URL.rstrip("/")
