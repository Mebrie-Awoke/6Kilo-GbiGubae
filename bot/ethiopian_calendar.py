"""Ethiopian (E.C.) calendar conversion and display helpers.

Uses the Ethiopian Amete Mihret epoch (JDN 1723856) and the
Beyene–Kudlek four-year cycle. Stored schedule timestamps remain UTC.
"""
from datetime import date, datetime, time, timedelta, tzinfo

ETHIOPIAN_EPOCH_JDN = 1723856
MONTHS = (
    "Meskerem", "Tikimt", "Hidar", "Tahsas", "Tir",
    "Yekatit", "Megabit", "Miyazya", "Ginbot", "Sene",
    "Hamle", "Nehase", "Pagume",
)


def is_leap_year(year: int) -> bool:
    return year % 4 == 3


def validate_ethiopian_date(year: int, month: int, day: int) -> None:
    if year < 1 or not 1 <= month <= 13:
        raise ValueError("Invalid Ethiopian year or month.")
    max_day = 6 if month == 13 and is_leap_year(year) else 5 if month == 13 else 30
    if not 1 <= day <= max_day:
        raise ValueError("Invalid day for the selected Ethiopian month.")


def to_gregorian(year: int, month: int, day: int) -> date:
    """Convert an Ethiopian calendar date to a Gregorian date."""
    validate_ethiopian_date(year, month, day)
    jdn = (
        ETHIOPIAN_EPOCH_JDN + 365 + 365 * (year - 1)
        + year // 4 + 30 * month + day - 31
    )
    return date.fromordinal(jdn - 1721425)


def from_gregorian(value: date) -> tuple[int, int, int]:
    """Convert a Gregorian date to (Ethiopian year, month, day)."""
    jdn = value.toordinal() + 1721425
    offset = jdn - ETHIOPIAN_EPOCH_JDN
    r = offset % 1461
    n = r % 365 + 365 * (r // 1460)
    year = 4 * (offset // 1461) + r // 365 - r // 1460
    return year, n // 30 + 1, n % 30 + 1


def format_ethiopian(value: datetime, tz: tzinfo) -> str:
    """Format a datetime in the configured local timezone and Ethiopian date."""
    local = value.astimezone(tz)
    year, month, day = from_gregorian(local.date())
    return f"{day:02d} {MONTHS[month - 1]} {year} E.C. · {local:%H:%M}"


def parse_ethiopian_datetime(value: str, tz: tzinfo) -> datetime:
    """Parse YYYY-MM-DD HH:MM as an Ethiopian date/time into aware local time."""
    try:
        date_text, time_text = value.strip().split()
        year_text, month_text, day_text = date_text.split("-")
        hour_text, minute_text = time_text.split(":")
        year, month, day = int(year_text), int(month_text), int(day_text)
        hour, minute = int(hour_text), int(minute_text)
        validate_ethiopian_date(year, month, day)
        if not 0 <= hour <= 23 or not 0 <= minute <= 59:
            raise ValueError("Invalid time.")
        gregorian = to_gregorian(year, month, day)
        return datetime.combine(gregorian, time(hour, minute), tzinfo=tz)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            "Use a valid Ethiopian date and time: YYYY-MM-DD HH:MM (E.C.)."
        ) from exc
