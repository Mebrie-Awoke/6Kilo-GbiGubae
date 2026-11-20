"""Pure helpers for calculating the next recurring schedule occurrence."""
import calendar
from datetime import datetime, timedelta

from croniter import croniter

from db.models import ScheduleType


def calculate_next_run(
    schedule_type: ScheduleType,
    scheduled_at: datetime,
    now: datetime,
    cron_expr: str | None = None,
) -> datetime | None:
    """Return the next future occurrence, preserving the original wall-clock time."""
    if schedule_type == ScheduleType.CUSTOM:
        if not cron_expr:
            return None
        return croniter.croniter(cron_expr, now).get_next(datetime)

    if schedule_type == ScheduleType.WEEKLY:
        candidate = scheduled_at + timedelta(weeks=1)
        while candidate <= now:
            candidate += timedelta(weeks=1)
        return candidate

    if schedule_type == ScheduleType.MONTHLY:
        candidate = scheduled_at
        while candidate <= now:
            year = candidate.year
            month = candidate.month + 1
            if month > 12:
                month = 1
                year += 1
            day = min(scheduled_at.day, calendar.monthrange(year, month)[1])
            candidate = scheduled_at.replace(year=year, month=month, day=day)
        return candidate

    return None
