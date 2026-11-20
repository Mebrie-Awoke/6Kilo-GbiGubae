"""Durable Telegram webhook inbox and update processor."""
import asyncio
import hmac
import logging
from datetime import datetime, timedelta

from aiogram import Bot, Dispatcher
from aiogram.types import Update
from sqlalchemy import and_, or_, select
from sqlalchemy.dialects.postgresql import insert

from db.models import TelegramUpdate
from db.session import AsyncSessionLocal

logger = logging.getLogger(__name__)
STALE_UPDATE_LOCK = timedelta(minutes=2)
MAX_UPDATE_ATTEMPTS = 10


async def persist_telegram_update(payload: dict) -> bool:
    """Insert an update once; duplicate Telegram webhook retries are harmless."""
    update_id = payload.get("update_id")
    if not isinstance(update_id, int):
        raise ValueError("Telegram update payload has no valid update_id.")

    statement = insert(TelegramUpdate).values(
        update_id=update_id,
        payload=payload,
        status="pending",
        attempts=0,
    ).on_conflict_do_nothing(index_elements=[TelegramUpdate.update_id])

    async with AsyncSessionLocal() as session:
        result = await session.execute(statement)
        await session.commit()
        return result.rowcount == 1


async def _claim_update() -> tuple[int, dict, int] | None:
    now = datetime.utcnow()
    stale_before = now - STALE_UPDATE_LOCK

    async with AsyncSessionLocal() as session:
        statement = (
            select(TelegramUpdate)
            .where(
                or_(
                    TelegramUpdate.status == "pending",
                    and_(
                        TelegramUpdate.status == "processing",
                        TelegramUpdate.locked_at < stale_before,
                    ),
                )
            )
            .order_by(TelegramUpdate.received_at)
            .with_for_update(skip_locked=True)
            .limit(1)
        )
        row = (await session.execute(statement)).scalar_one_or_none()
        if row is None:
            return None

        row.status = "processing"
        row.locked_at = now
        row.attempts += 1
        claimed = (row.update_id, dict(row.payload), row.attempts)
        await session.commit()
        return claimed


async def _finish_update(update_id: int, status: str, error: str | None = None) -> None:
    async with AsyncSessionLocal() as session:
        row = await session.get(TelegramUpdate, update_id)
        if row is None:
            return
        row.status = status
        row.last_error = error[:4000] if error else None
        row.locked_at = None
        if status == "done":
            row.processed_at = datetime.utcnow()
        await session.commit()


async def telegram_update_worker(bot: Bot, dispatcher: Dispatcher) -> None:
    """Process persisted updates and recover abandoned work after restarts."""
    logger.info("Persistent Telegram update worker started")
    while True:
        try:
            claimed = await _claim_update()
            if claimed is None:
                await asyncio.sleep(1)
                continue

            update_id, payload, attempts = claimed
            try:
                update = Update.model_validate(payload)
                await dispatcher.feed_update(bot, update)
                await _finish_update(update_id, "done")
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                logger.exception("Telegram update %s failed", update_id)
                next_status = "pending" if attempts < MAX_UPDATE_ATTEMPTS else "failed"
                await _finish_update(update_id, next_status, str(exc))
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Telegram update worker iteration failed")
            await asyncio.sleep(3)


def verify_webhook_secret(received: str | None, expected: str) -> bool:
    return bool(received and expected and hmac.compare_digest(received, expected))
