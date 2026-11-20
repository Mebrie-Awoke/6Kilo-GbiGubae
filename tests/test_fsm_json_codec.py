"""Tests for persistent FSM JSON value conversion."""
import unittest
from datetime import date, datetime

from db.models import ScheduleType
from storage.json_codec import decode_fsm_value, encode_fsm_value


class FSMJsonCodecTests(unittest.TestCase):
    def test_datetime_round_trip(self):
        value = {"selected_date": datetime(2026, 11, 20, 12, 30)}
        self.assertEqual(decode_fsm_value(encode_fsm_value(value)), value)

    def test_date_round_trip(self):
        value = {"date": date(2026, 11, 20)}
        self.assertEqual(decode_fsm_value(encode_fsm_value(value)), value)

    def test_schedule_type_round_trip(self):
        value = {"schedule_type": ScheduleType.MONTHLY}
        self.assertEqual(decode_fsm_value(encode_fsm_value(value)), value)

    def test_nested_data_round_trip(self):
        value = {
            "batches": [1, 2],
            "nested": {"date": datetime(2026, 11, 20, 8, 0)},
        }
        self.assertEqual(decode_fsm_value(encode_fsm_value(value)), value)


if __name__ == "__main__":
    unittest.main()
