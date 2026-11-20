"""Application entry point: Telegram webhook on Render, polling locally."""
import asyncio
import logging
import os

from aiohttp import web
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application

from bot.config import load_settings
from bot.handlers import router
from bot.scheduler import scheduler_loop
from bot.storage import JsonStore

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
WEBHOOK_PATH = "/telegram/webhook"


async def health(request: web.Request) -> web.Response:
    return web.json_response({"status": "ok", "service": "6Kilo GbiGubae"})


async def readiness(request: web.Request) -> web.Response:
    store: JsonStore = request.app["store"]
    try:
        await store.health_check()
        return web.json_response({"status": "ready", "storage": "writable"})
    except Exception:
        logger.exception("Readiness check failed")
        return web.json_response({"status": "not_ready", "storage": "unavailable"}, status=503)


async def configure_commands(bot: Bot, admin_id: int) -> None:
    await bot.set_my_commands([
        BotCommand(command="start", description="ምዝገባ / እንደገና ጀምር"),
        BotCommand(command="profile", description="መገለጫዎን ይመልከቱ"),
        BotCommand(command="edit_batch", description="የትምህርት ዓመት ይቀይሩ"),
        BotCommand(command="help", description="ትዕዛዞችን ይመልከቱ"),
    ])
    await bot.set_my_commands([
        BotCommand(command="start", description="የአስተዳዳሪ ማዕከል ይክፈቱ"),
        BotCommand(command="admin", description="የአስተዳዳሪ ማዕከል ይክፈቱ"),
        BotCommand(command="menu", description="የአስተዳዳሪ ማዕከል ይክፈቱ"),
        BotCommand(command="users", description="የአባላት ሪፖርት"),
        BotCommand(command="broadcast", description="ማስታወቂያ ይላኩ"),
        BotCommand(command="schedule", description="መልዕክት ያቅዱ"),
        BotCommand(command="schedules", description="የታቀዱ መልዕክቶችን ይመልከቱ"),
        BotCommand(command="cancel_schedule", description="መርሐግብር ይሰርዙ"),
        BotCommand(command="help", description="ትዕዛዞችን ይመልከቱ"),
        BotCommand(command="cancel", description="አሁን ያለውን ሂደት ያቋርጡ"),
    ], scope=BotCommandScopeChat(chat_id=admin_id))


async def run_webhook(bot: Bot, dp: Dispatcher, store: JsonStore, settings) -> None:
    await bot.set_webhook(
        url=f"{settings.webhook_base_url}{WEBHOOK_PATH}",
        secret_token=settings.webhook_secret,
        allowed_updates=dp.resolve_used_update_types(),
        drop_pending_updates=False,
    )
    app = web.Application(client_max_size=1024 * 1024)
    app["store"] = store
    app.router.add_get("/", health)
    app.router.add_get("/health/ready", readiness)
    SimpleRequestHandler(
        dispatcher=dp,
        bot=bot,
        secret_token=settings.webhook_secret,
    ).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", settings.port)
    await site.start()
    logger.info("Webhook server listening on port %s", settings.port)
    try:
        await asyncio.Event().wait()
    finally:
        await runner.cleanup()


async def main() -> None:
    settings = load_settings()
    store = JsonStore(settings.data_file)
    await store.health_check()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    dp["settings"] = settings
    dp["store"] = store

    scheduler_task = asyncio.create_task(scheduler_loop(bot, store, settings))
    try:
        await configure_commands(bot, settings.super_admin_id)
        if settings.webhook_base_url:
            await run_webhook(bot, dp, store, settings)
        else:
            logger.info("Starting local long-polling mode.")
            await bot.delete_webhook(drop_pending_updates=False)
            await dp.start_polling(bot)
    finally:
        scheduler_task.cancel()
        await asyncio.gather(scheduler_task, return_exceptions=True)
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
