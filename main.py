"""Application entry point and lightweight Render health endpoints."""
import asyncio
import logging
import os

from aiohttp import web
from sqlalchemy import text

from db.session import engine
from loader import bot, dp
import handlers.users  # noqa: F401
import handlers.admin  # noqa: F401
import handlers.schedule  # noqa: F401
from handlers.startup import seed_batches

logger = logging.getLogger(__name__)


async def health_check(request: web.Request) -> web.Response:
    """Liveness check: the web process is responding."""
    return web.json_response({"status": "alive"})


async def readiness_check(request: web.Request) -> web.Response:
    """Readiness check: verify that PostgreSQL is reachable."""
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


async def ping(request: web.Request) -> web.Response:
    return web.json_response({"message": "pong"})


async def start_web_server() -> web.AppRunner:
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health/ready", readiness_check)
    app.router.add_get("/ping", ping)

    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.getenv("PORT", "8080"))
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    logger.info("Health server started on port %s", port)
    return runner


async def main() -> None:
    from services.scheduler import scheduler_loop
    from utils.set_bot_commands import set_default_commands, set_admin_commands

    runner = await start_web_server()
    scheduler_task = None

    try:
        await seed_batches()
        await set_default_commands(bot)
        await set_admin_commands(bot)

        scheduler_task = asyncio.create_task(
            scheduler_loop(bot),
            name="schedule-dispatcher",
        )

        logger.info("Telegram bot starting")
        await bot.delete_webhook(drop_pending_updates=True)
        await dp.start_polling(bot, close_bot_session=False)
    finally:
        if scheduler_task:
            scheduler_task.cancel()
            await asyncio.gather(scheduler_task, return_exceptions=True)

        # Finish in-flight schedule dispatches before draining the worker queue.
        from services import scheduler as scheduler_service
        if scheduler_service.schedule_tasks:
            await asyncio.gather(
                *list(scheduler_service.schedule_tasks),
                return_exceptions=True,
            )
        if scheduler_service.broadcast_manager is not None:
            await scheduler_service.broadcast_manager.stop()

        await bot.session.close()
        await engine.dispose()
        await runner.cleanup()


if __name__ == "__main__":
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    )
    asyncio.run(main())
