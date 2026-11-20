"""Database-backed recurring schedule and broadcast delivery worker."""
import asyncio
import logging
from datetime import datetime, timedelta

from aiogram import Bot
from aiogram.exceptions import (
    TelegramAPIError,
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from sqlalchemy import and_, func, or_, select
from sqlalchemy.dialects.postgresql import insert

from db.models import (
    BroadcastDelivery,
    BroadcastRun,
    Schedule,
    ScheduleType,
    User,
    schedule_batch_association,
)
from db.session import AsyncSessionLocal
from services.schedule_time import calculate_next_run
from utils.message_utils import personalize_message

logger = logging.getLogger(__name__)

MAX_DELIVERY_ATTEMPTS = 5
DELIVERY_BATCH_SIZE = 100
STALE_DELIVERY_LOCK = timedelta(minutes=15)
GLOBAL_SEND_INTERVAL = 1 / 25


async def materialize_due_schedules(now: datetime | None = None) -> int:
    """Create durable runs and recipient rows for all schedules currently due."""
    now = now or datetime.utcnow()
    created_runs = 0

    async with AsyncSessionLocal() as session:
        schedules = (
            await session.execute(
                select(Schedule)
                .where(Schedule.is_active.is_(True), Schedule.next_run <= now)
                .order_by(Schedule.next_run)
                .with_for_update(skip_locked=True)
                .limit(50)
            )
        ).scalars().all()

        for schedule in schedules:
            scheduled_for = schedule.next_run
            run_statement = (
                insert(BroadcastRun)
                .values(
                    schedule_id=schedule.id,
                    scheduled_for=scheduled_for,
                    status="pending",
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        BroadcastRun.schedule_id,
                        BroadcastRun.scheduled_for,
                    ]
                )
                .returning(BroadcastRun.id)
            )
            run_id = (await session.execute(run_statement)).scalar_one_or_none()

            if run_id is not None:
                message = schedule.caption if schedule.media_type else schedule.message
                recipient_rows = (
                    await session.execute(
                        select(User.user_id, User.full_name)
                        .join(
                            schedule_batch_association,
                            User.batch_id == schedule_batch_association.c.batch_id,
                        )
                        .where(
                            schedule_batch_association.c.schedule_id == schedule.id
                        )
                    )
                ).all()

                if recipient_rows:
                    deliveries = [
                        {
                            "run_id": run_id,
                            "user_id": user_id,
                            "full_name": full_name,
                            "message": message,
                            "media_type": schedule.media_type,
                            "media_file_id": schedule.media_file_id,
                            "status": "pending",
                            "attempts": 0,
                        }
                        for user_id, full_name in recipient_rows
                    ]
                    await session.execute(
                        insert(BroadcastDelivery)
                        .values(deliveries)
                        .on_conflict_do_nothing(
                            index_elements=[
                                BroadcastDelivery.run_id,
                                BroadcastDelivery.user_id,
                            ]
                        )
                    )
                else:
                    await session.execute(
                        BroadcastRun.__table__.update()
                        .where(BroadcastRun.id == run_id)
                        .values(status="completed", completed_at=now)
                    )
                created_runs += 1

            try:
                next_run = calculate_next_run(
                    schedule.type,
                    scheduled_for,
                    now,
                    schedule.cron_expr,
                    schedule.monthly_day,
                )
            except Exception:
                logger.exception("Could not calculate next run for schedule #%s", schedule.id)
                next_run = None

            if next_run is None:
                schedule.is_active = False
            else:
                schedule.next_run = next_run

        await session.commit()

    if created_runs:
        logger.info("Materialized %s scheduled broadcast run(s)", created_runs)
    return created_runs


async def _send_delivery(bot: Bot, delivery: dict) -> tuple[bool, str | None, bool]:
    """Return (sent, error, retryable)."""
    text = delivery["message"]
    full_name = delivery["full_name"]
    if full_name and text:
        text = personalize_message(text, full_name)
    elif full_name and not text:
        from html import escape
        text = f"ሰላም {escape(full_name)}"

    for attempt in range(MAX_DELIVERY_ATTEMPTS):
        try:
            media_type = delivery["media_type"]
            if media_type == "photo":
                await bot.send_photo(
                    chat_id=delivery["user_id"],
                    photo=delivery["media_file_id"],
                    caption=text,
                    parse_mode="HTML",
                )
            elif media_type == "video":
                await bot.send_video(
                    chat_id=delivery["user_id"],
                    video=delivery["media_file_id"],
                    caption=text,
                    parse_mode="HTML",
                )
            elif media_type == "document":
                await bot.send_document(
                    chat_id=delivery["user_id"],
                    document=delivery["media_file_id"],
                    caption=text,
                    parse_mode="HTML",
                )
            elif media_type is None:
                if not text:
                    return False, "Empty text message.", False
                await bot.send_message(
                    chat_id=delivery["user_id"],
                    text=text,
                    parse_mode="HTML",
                    disable_web_page_preview=True,
                )
            else:
                return False, f"Unsupported media type: {media_type}", False
            return True, None, False

        except TelegramRetryAfter as exc:
            await asyncio.sleep(float(exc.retry_after) + 0.5)
        except TelegramForbiddenError as exc:
            return False, str(exc), False
        except TelegramBadRequest as exc:
            return False, str(exc), False
        except TelegramAPIError as exc:
            if attempt + 1 >= MAX_DELIVERY_ATTEMPTS:
                return False, str(exc), True
            await asyncio.sleep(min(2 ** attempt, 30))
        except Exception as exc:
            if attempt + 1 >= MAX_DELIVERY_ATTEMPTS:
                return False, str(exc), True
            await asyncio.sleep(min(2 ** attempt, 30))

    return False, "Retry limit reached.", True


async def _claim_deliveries(limit: int = DELIVERY_BATCH_SIZE) -> list[dict]:
    now = datetime.utcnow()
    stale_before = now - STALE_DELIVERY_LOCK
    async with AsyncSessionLocal() as session:
        statement = (
            select(BroadcastDelivery)
            .where(
                or_(
                    BroadcastDelivery.status == "pending",
                    and_(
                        BroadcastDelivery.status == "processing",
                        BroadcastDelivery.locked_at < stale_before,
                    ),
                )
            )
            .order_by(BroadcastDelivery.id)
            .with_for_update(skip_locked=True)
            .limit(limit)
        )
        rows = (await session.execute(statement)).scalars().all()
        claimed = []
        for row in rows:
            row.status = "processing"
            row.locked_at = now
            row.attempts += 1
            claimed.append(
                {
                    "id": row.id,
                    "run_id": row.run_id,
                    "user_id": row.user_id,
                    "full_name": row.full_name,
                    "message": row.message,
                    "media_type": row.media_type,
                    "media_file_id": row.media_file_id,
                    "attempts": row.attempts,
                }
            )
        await session.commit()
        return claimed


async def _record_delivery(
    delivery_id: int,
    run_id: int,
    sent: bool,
    error: str | None,
    retryable: bool,
    attempts: int,
) -> None:
    now = datetime.utcnow()
    async with AsyncSessionLocal() as session:
        row = await session.get(BroadcastDelivery, delivery_id)
        if row is None:
            return
        if sent:
            row.status = "sent"
            row.sent_at = now
            row.last_error = None
        elif retryable and attempts < MAX_DELIVERY_ATTEMPTS:
            row.status = "pending"
            row.last_error = (error or "Temporary delivery failure.")[:4000]
        else:
            row.status = "failed"
            row.last_error = (error or "Delivery failed.")[:4000]
        row.locked_at = None

        remaining = await session.scalar(
            select(func.count(BroadcastDelivery.id)).where(
                BroadcastDelivery.run_id == run_id,
                BroadcastDelivery.status.in_(["pending", "processing"]),
            )
        )
        if remaining == 0:
            failed = await session.scalar(
                select(func.count(BroadcastDelivery.id)).where(
                    BroadcastDelivery.run_id == run_id,
                    BroadcastDelivery.status == "failed",
                )
            )
            run = await session.get(BroadcastRun, run_id)
            if run:
                run.status = "completed_with_errors" if failed else "completed"
                run.completed_at = now
        await session.commit()


async def process_pending_deliveries(bot: Bot, max_deliveries: int = 5000) -> int:
    """Send durable delivery records; unfinished work is picked up next run."""
    processed = 0
    while processed < max_deliveries:
        batch = await _claim_deliveries(min(DELIVERY_BATCH_SIZE, max_deliveries - processed))
        if not batch:
            break

        for delivery in batch:
            sent, error, retryable = await _send_delivery(bot, delivery)
            await _record_delivery(
                delivery["id"],
                delivery["run_id"],
                sent,
                error,
                retryable,
                delivery["attempts"],
            )
            processed += 1
            await asyncio.sleep(GLOBAL_SEND_INTERVAL)

    logger.info("Processed %s durable broadcast deliveries", processed)
    return processed


async def run_scheduled_broadcasts(bot: Bot) -> tuple[int, int]:
    """Materialize due schedules and resume any outstanding deliveries."""
    runs = await materialize_due_schedules()
    deliveries = await process_pending_deliveries(bot)
    return runs, deliveries
