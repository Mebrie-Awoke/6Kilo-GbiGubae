"""Webhook application entry point for Render."""
import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from sqlalchemy import text

from config import WEBHOOK_BASE_URL, WEBHOOK_SECRET
from db.session import engine
from loader import bot, dp
import handlers.users  # noqa: F401
import handlers.admin  # noqa: F401
import handlers.schedule  # noqa: F401
from handlers.startup import seed_batches
from services.telegram_updates import (
    persist_telegram_update,
    telegram_update_worker,
    verify_webhook_secret,
)

logger = logging.getLogger(__name__)
WEBHOOK_PATH = "/telegram/webhook"


async def health_check(request: web.Request) -> web.Response:
    return web.json_response({"status": "alive"})


async def readiness_check(request: web.Request) -> web.Response:
    try:
        async with engine.connect() as connection:
            await connection.execute(text("SELECT 1"))
        return web.json_response({"status": "ready", "database": "connected"})
    except Exception:
        logger.exception("Readiness check failed")
        return web.json_response(
            {"status": "not_ready", "database": "unavailable"},
            status=503,
        )


async def telegram_webhook(request: web.Request) -> web.Response:
    received_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if not verify_webhook_secret(received_secret, request.app["webhook_secret"]):
        return web.json_response({"ok": False}, status=403)

    try:
        payload = await request.json()
        await persist_telegram_update(payload)
    except (ValueError, TypeError):
        logger.warning("Rejected invalid Telegram webhook payload")
        return web.json_response({"ok": False, "error": "invalid update"}, status=400)
    except Exception:
        # Returning non-2xx asks Telegram to retry; the DB inbox also deduplicates
        # updates by update_id in case the insert succeeded but the response failed.
        logger.exception("Could not persist Telegram webhook update")
        return web.json_response({"ok": False}, status=503)

    return web.json_response({"ok": True, "queued": True})


async def start_web_server() -> web.AppRunner:
    app = web.Application(client_max_size=1024 * 1024)
    app["webhook_secret"] = WEBHOOK_SECRET
    app.router.add_get("/", health_check)
    app.router.add_get("/health/ready", readiness_check)
    app.router.add_post(WEBHOOK_PATH, telegram_webhook)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Webhook server listening on port %s", port)
    return runner


async def main() -> None:
    if not WEBHOOK_SECRET or not WEBHOOK_BASE_URL:
        raise RuntimeError(
            "Set WEBHOOK_SECRET and WEBHOOK_BASE_URL (or use Render's RENDER_EXTERNAL_URL)."
        )

    runner = await start_web_server()
    update_worker = None

    try:
        await seed_batches()
        from utils.set_bot_commands import set_default_commands, set_admin_commands
        await set_default_commands(bot)
        await set_admin_commands(bot)

        webhook_url = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"
        await bot.set_webhook(
            url=webhook_url,
            secret_token=WEBHOOK_SECRET,
            allowed_updates=dp.resolve_used_update_types(),
            drop_pending_updates=False,
        )
        logger.info("Telegram webhook configured at %s", webhook_url)

        update_worker = asyncio.create_task(
            telegram_update_worker(bot, dp),
            name="telegram-update-worker",
        )
        # Keep the HTTP server alive; webhook updates are persisted before ACK.
        await asyncio.Event().wait()
    finally:
        if update_worker:
            update_worker.cancel()
            await asyncio.gather(update_worker, return_exceptions=True)

        try:
            await bot.delete_webhook(drop_pending_updates=False)
        except Exception:
            logger.exception("Could not clear webhook during shutdown")

        await dp.storage.close()
        await bot.session.close()
        await engine.dispose()
        await runner.cleanup()


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    asyncio.run(main())
