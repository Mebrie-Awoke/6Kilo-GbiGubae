"""FastAPI application and Telegram bot lifecycle."""
import asyncio
import logging
import secrets
from contextlib import asynccontextmanager

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import BotCommand, BotCommandScopeChat, Update
from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse

from bot.config import load_settings
from bot.handlers import router
from bot.scheduler import scheduler_loop
from bot.storage import MongoStore

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)
WEBHOOK_PATH = "/telegram/webhook"


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
        BotCommand(command="add_admin", description="Grant administrator access (super admin)"),
        BotCommand(command="remove_admin", description="Revoke administrator access (super admin)"),
        BotCommand(command="admins", description="List additional administrators (super admin)"),
    ], scope=BotCommandScopeChat(chat_id=admin_id))


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = load_settings()
    store = MongoStore(settings.mongodb_uri, settings.mongodb_database)
    await store.connect()

    bot = Bot(
        token=settings.bot_token,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())
    dp.include_router(router)
    dp["settings"] = settings
    dp["store"] = store

    app.state.settings = settings
    app.state.store = store
    app.state.bot = bot
    app.state.dispatcher = dp

    scheduler_task = asyncio.create_task(scheduler_loop(bot, store, settings))
    polling_task = None
    try:
        await configure_commands(bot, settings.super_admin_id)
        if settings.webhook_base_url:
            await bot.set_webhook(
                url=f"{settings.webhook_base_url}{WEBHOOK_PATH}",
                secret_token=settings.webhook_secret,
                allowed_updates=dp.resolve_used_update_types(),
                drop_pending_updates=False,
            )
            logger.info("Telegram webhook configured.")
        else:
            await bot.delete_webhook(drop_pending_updates=False)
            polling_task = asyncio.create_task(dp.start_polling(bot))
            logger.info("Telegram polling started.")
        yield
    finally:
        if polling_task:
            polling_task.cancel()
            await asyncio.gather(polling_task, return_exceptions=True)
        scheduler_task.cancel()
        await asyncio.gather(scheduler_task, return_exceptions=True)
        # Keep the webhook registered during Render restarts and deployments.
        # Telegram will retry pending updates while the new instance starts.
        await bot.session.close()
        await store.close()


app = FastAPI(
    title="6Kilo GbiGubae API",
    description="FastAPI service for the 6Kilo GbiGubae Telegram bot.",
    version="2.0.0",
    lifespan=lifespan,
)


@app.get("/")
async def health():
    return {"status": "ok", "service": "6Kilo GbiGubae API"}


@app.get("/health/ready")
async def readiness(request: Request):
    try:
        await request.app.state.store.health_check()
        return {"status": "ready", "database": "connected"}
    except Exception:
        logger.exception("Readiness check failed")
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "unavailable"},
        )


@app.post(WEBHOOK_PATH)
async def telegram_webhook(
    request: Request,
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
):
    settings = request.app.state.settings
    if not settings.webhook_secret or not secrets.compare_digest(
        x_telegram_bot_api_secret_token or "",
        settings.webhook_secret,
    ):
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    update = Update.model_validate(
        await request.json(),
        context={"bot": request.app.state.bot},
    )
    await request.app.state.dispatcher.feed_update(
        request.app.state.bot,
        update,
    )
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    import os

    uvicorn.run("main:app", host="0.0.0.0", port=int(os.getenv("PORT", "8080")))
