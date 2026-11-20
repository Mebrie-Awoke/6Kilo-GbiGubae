"""Regression tests for recurring schedule calculations."""
import unittest
from datetime import datetime

from db.models import ScheduleType
from services.schedule_time import calculate_next_run


class ScheduleTimeTests(unittest.TestCase):
    def test_weekly_preserves_original_time(self):
        scheduled = datetime(2026, 11, 20, 9, 30)
        now = datetime(2026, 11, 21, 12, 0)
        self.assertEqual(
            calculate_next_run(ScheduleType.WEEKLY, scheduled, now),
            datetime(2026, 11, 27, 9, 30),
        )

    def test_weekly_skips_missed_occurrences(self):
        scheduled = datetime(2026, 10, 1, 8, 0)
        now = datetime(2026, 11, 20, 10, 0)
        self.assertEqual(
            calculate_next_run(ScheduleType.WEEKLY, scheduled, now),
            datetime(2026, 11, 26, 8, 0),
        )

    def test_monthly_handles_month_end(self):
        scheduled = datetime(2026, 1, 31, 9, 0)
        now = datetime(2026, 2, 1, 0, 0)
        self.assertEqual(
            calculate_next_run(ScheduleType.MONTHLY, scheduled, now),
            datetime(2026, 2, 28, 9, 0),
        )

    def test_monthly_advances_to_next_valid_month_after_missed_run(self):
        scheduled = datetime(2026, 1, 31, 9, 0)
        now = datetime(2026, 3, 1, 0, 0)
        self.assertEqual(
            calculate_next_run(ScheduleType.MONTHLY, scheduled, now),
            datetime(2026, 3, 31, 9, 0),
        )

    def test_monthly_anchor_prevents_drift_after_february(self):
        scheduled = datetime(2026, 2, 28, 9, 0)
        now = datetime(2026, 3, 1, 0, 0)
        self.assertEqual(
            calculate_next_run(
                ScheduleType.MONTHLY,
                scheduled,
                now,
                monthly_day=31,
            ),
            datetime(2026, 3, 31, 9, 0),
        )

    def test_custom_cron_returns_next_future_occurrence(self):
        scheduled = datetime(2026, 11, 20, 8, 0)
        now = datetime(2026, 11, 20, 10, 0)
        self.assertEqual(
            calculate_next_run(
                ScheduleType.CUSTOM,
                scheduled,
                now,
                "0 9 * * 1",
            ),
            datetime(2026, 11, 23, 9, 0),
        )

    def test_custom_without_expression_is_disabled(self):
        self.assertIsNone(
            calculate_next_run(
                ScheduleType.CUSTOM,
                datetime(2026, 11, 20, 8, 0),
                datetime(2026, 11, 20, 10, 0),
            )
        )


if __name__ == "__main__":
    unittest.main()
