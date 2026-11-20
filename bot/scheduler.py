"""Persistent scheduler with a MongoDB lease to prevent duplicate workers."""
import asyncio
import logging
import uuid
from datetime import datetime, timezone

from aiogram.exceptions import TelegramBadRequest, TelegramForbiddenError, TelegramRetryAfter

from bot.config import Settings
from bot.storage import MongoStore

logger = logging.getLogger(__name__)


async def deliver_due_messages(bot, store: MongoStore, settings: Settings) -> None:
    due = await store.due_schedules(datetime.now(timezone.utc))
    for schedule in due:
        recipients = await store.list_users(
            None if schedule["batch"].lower() == "all" else schedule["batch"]
        )
        already_handled = set(schedule.get("sent_to", [])) | set(schedule.get("failed_to", []))
        for recipient in recipients:
            user_id = recipient["telegram_id"]
            if user_id in already_handled:
                continue
            try:
                await bot.send_message(user_id, schedule["message"], parse_mode=None)
                await store.record_delivery(schedule["id"], user_id, success=True)
                await asyncio.sleep(0.05)
            except (TelegramForbiddenError, TelegramBadRequest) as exc:
                logger.info("Permanent delivery failure for user %s: %s", user_id, exc)
                await store.record_delivery(schedule["id"], user_id, success=False)
            except TelegramRetryAfter as exc:
                logger.warning(
                    "Telegram rate limit reached; schedule #%s will resume later",
                    schedule["id"],
                )
                await asyncio.sleep(exc.retry_after)
                break
            except Exception as exc:
                logger.exception("Temporary delivery failure for schedule #%s", schedule["id"])
                await store.fail_schedule(schedule["id"], str(exc))
                break
        else:
            await store.complete_schedule(schedule["id"])


async def _renew_lock(store: MongoStore, owner: str) -> None:
    while True:
        await asyncio.sleep(15)
        if not await store.renew_scheduler_lock(owner):
            logger.error("Scheduler lease was lost; stopping this worker.")
            return


async def scheduler_loop(bot, store: MongoStore, settings: Settings) -> None:
    owner = str(uuid.uuid4())
    logger.info("Persistent scheduler started.")
    while True:
        try:
            if await store.acquire_scheduler_lock(owner):
                heartbeat = asyncio.create_task(_renew_lock(store, owner))
                try:
                    await deliver_due_messages(bot, store, settings)
                finally:
                    heartbeat.cancel()
                    await asyncio.gather(heartbeat, return_exceptions=True)
                    await store.release_scheduler_lock(owner)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Scheduler iteration failed")
        await asyncio.sleep(15)
