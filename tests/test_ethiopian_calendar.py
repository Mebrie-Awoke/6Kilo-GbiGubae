import unittest
from datetime import date
from zoneinfo import ZoneInfo

from bot.ethiopian_calendar import (
    from_gregorian,
    is_leap_year,
    parse_ethiopian_datetime,
    to_gregorian,
)


class EthiopianCalendarTests(unittest.TestCase):
    def test_known_new_year_conversion(self):
        self.assertEqual(to_gregorian(2016, 1, 1), date(2023, 9, 12))
        self.assertEqual(from_gregorian(date(2023, 9, 12)), (2016, 1, 1))

    def test_schedule_date_conversion(self):
        # Hidar 13, 2019 E.C. is November 22, 2026 G.C.
        local = parse_ethiopian_datetime("2019-03-13 09:30", ZoneInfo("Africa/Addis_Ababa"))
        self.assertEqual(local.date(), date(2026, 11, 22))
        self.assertEqual((local.hour, local.minute), (9, 30))

    def test_pagume_leap_day(self):
        self.assertTrue(is_leap_year(2015))
        self.assertEqual(to_gregorian(2015, 13, 6), date(2023, 9, 11))

    def test_invalid_pagume_day_is_rejected(self):
        with self.assertRaises(ValueError):
            to_gregorian(2016, 13, 6)

    def test_invalid_month_and_day_are_rejected(self):
        with self.assertRaises(ValueError):
            to_gregorian(2019, 14, 1)
        with self.assertRaises(ValueError):
            to_gregorian(2019, 1, 31)


if __name__ == "__main__":
    unittest.main()
