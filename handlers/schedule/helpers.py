# handlers/schedule/helpers.py
"""Helper functions for schedule management."""
from datetime import datetime, timedelta
import logging

from sqlalchemy import select

from config import SUPER_ADMIN_ID
from db.models import Schedule, User, ScheduleType
from db.session import AsyncSessionLocal
from db.permissions import is_admin_user

logger = logging.getLogger(__name__)


def format_12hour(dt: datetime) -> str:
    """Convert a naive UTC datetime to Ethiopia time and format as 12-hour."""
    ethiopia_time = dt + timedelta(hours=3)
    period = "AM" if ethiopia_time.hour < 12 else "PM"
    hour = ethiopia_time.hour % 12 or 12
    time_str = (
        f"{hour}:{ethiopia_time.minute:02d} {period}"
        if ethiopia_time.minute
        else f"{hour}:00 {period}"
    )
    return f"{ethiopia_time.strftime('%b %d, %Y')} at {time_str} (Ethiopia Time)"


async def ensure_user_exists(user_id: int, username: str | None = None) -> bool:
    """Return True only for an existing admin or the configured super admin.

    Unknown Telegram users are recorded as regular users, but are never granted
    administrative access by virtue of being new.
    """
    async with AsyncSessionLocal() as session:
        try:
            result = await session.execute(
                select(User).where(User.user_id == user_id)
            )
            user = result.scalar_one_or_none()

            if user is None:
                is_super_admin = user_id == SUPER_ADMIN_ID
                session.add(
                    User(
                        user_id=user_id,
                        username=username or "Unknown",
                        full_name=None,
                        is_admin=is_super_admin,
                        join_date=datetime.utcnow(),
                    )
                )
                await session.commit()
                logger.info(
                    "Created user record for Telegram ID %s (super_admin=%s)",
                    user_id,
                    is_super_admin,
                )
                return is_super_admin

            return is_admin_user(user_id, user.is_admin, SUPER_ADMIN_ID)
        except Exception:
            await session.rollback()
            logger.exception("Could not verify admin access for Telegram ID %s", user_id)
            return False


async def save_schedule(data: dict, admin_id: int) -> Schedule | None:
    """Save a new schedule and its selected batch associations."""
    from db.models import schedule_batch_association

    async with AsyncSessionLocal() as session:
        try:
            message_text = data.get("message_text")
            media_type = data.get("media_type")
            media_file_id = data.get("media_file_id")
            caption = data.get("caption")

            if not message_text and not media_file_id:
                logger.error("Schedule save rejected: neither text nor media supplied")
                return None

            sched = Schedule(
                message=message_text,
                media_type=media_type,
                media_file_id=media_file_id,
                caption=caption,
                type=data["schedule_type"],
                next_run=data["next_run"],
                monthly_day=(
                    data["next_run"].day
                    if data["schedule_type"] == ScheduleType.MONTHLY
                    else None
                ),
                admin_id=admin_id,
                is_active=True,
            )
            session.add(sched)
            await session.flush()

            for batch_id in data["batches"]:
                await session.execute(
                    schedule_batch_association.insert().values(
                        schedule_id=sched.id,
                        batch_id=batch_id,
                    )
                )

            await session.commit()
            logger.info("Schedule #%s saved successfully", sched.id)
            return sched
        except Exception:
            await session.rollback()
            logger.exception("Schedule save failed")
            return None
