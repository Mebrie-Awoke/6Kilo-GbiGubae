"""Environment configuration."""
from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    bot_token: str
    super_admin_id: int
    mongodb_uri: str
    mongodb_database: str
    timezone: str
    batches: tuple[str, ...]
    webhook_secret: str | None
    webhook_base_url: str | None
    port: int


def load_settings() -> Settings:
    token = os.getenv("BOT_TOKEN") or os.getenv("TG_BOT_TOKEN")
    if not token:
        raise RuntimeError("BOT_TOKEN is required.")

    try:
        admin_id = int(os.getenv("SUPER_ADMIN_ID", "").strip())
    except ValueError as exc:
        raise RuntimeError("SUPER_ADMIN_ID must be a numeric Telegram user ID.") from exc
    if admin_id <= 0:
        raise RuntimeError("SUPER_ADMIN_ID must be a positive Telegram user ID.")

    mongodb_uri = os.getenv("MONGODB_URI", "").strip()
    if not mongodb_uri:
        raise RuntimeError("MONGODB_URI is required. Add your MongoDB Atlas connection string.")

    batches = tuple(
        item.strip()
        for item in os.getenv(
            "BATCHES",
            "1st Year,2nd Year,3rd Year,4th Year,5th Year,6th Year",
        ).split(",")
        if item.strip()
    )
    if not batches:
        raise RuntimeError("Configure at least one batch in BATCHES.")

    base_url = (
        os.getenv("WEBHOOK_BASE_URL")
        or os.getenv("RENDER_EXTERNAL_URL")
        or ""
    ).rstrip("/")
    secret = os.getenv("WEBHOOK_SECRET") or None
    if base_url and not secret:
        raise RuntimeError("WEBHOOK_SECRET is required when webhook mode is enabled.")
    if secret and (
        len(secret) > 256
        or not all(char.isalnum() or char in "_-" for char in secret)
    ):
        raise RuntimeError("WEBHOOK_SECRET may contain only letters, numbers, underscores and hyphens.")

    return Settings(
        bot_token=token,
        super_admin_id=admin_id,
        mongodb_uri=mongodb_uri,
        mongodb_database=os.getenv("MONGODB_DATABASE", "gbigubae_bot").strip(),
        timezone=os.getenv("TIMEZONE", "Africa/Addis_Ababa"),
        batches=batches,
        webhook_secret=secret,
        webhook_base_url=base_url or None,
        port=int(os.getenv("PORT", "8080")),
    )
