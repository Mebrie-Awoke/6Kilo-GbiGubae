"""Application configuration loaded from environment variables."""
import os

from dotenv import load_dotenv

from db.url import normalize_async_database_url

load_dotenv()

BOT_TOKEN = os.getenv("TG_BOT_TOKEN") or os.getenv("BOT_TOKEN")

_super_admin_id = os.getenv("SUPER_ADMIN_ID")
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
