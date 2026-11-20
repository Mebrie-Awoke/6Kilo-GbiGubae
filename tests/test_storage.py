import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from bot.storage import JsonStore


class JsonStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.store = JsonStore(Path(self.temp_dir.name) / "data.json")

    async def asyncTearDown(self):
        self.temp_dir.cleanup()

    async def test_user_storage_keeps_only_name_and_batch(self):
        await self.store.save_user(12345, "Abebe", "1st Year")
        self.assertEqual(
            await self.store.get_user(12345),
            {"name": "Abebe", "batch": "1st Year"},
        )
        self.assertEqual(
            await self.store.list_users("1st Year"),
            [{"telegram_id": 12345, "name": "Abebe", "batch": "1st Year"}],
        )

    async def test_schedule_can_be_cancelled(self):
        await self.store.create_schedule(
            batch="all",
            message="Test announcement",
            send_at=datetime(2030, 1, 1, tzinfo=timezone.utc),
            created_by=1,
        )
        self.assertTrue(await self.store.cancel_schedule(1))
        self.assertEqual(await self.store.list_schedules(), [])

    async def test_due_delivery_progress_is_persisted(self):
        await self.store.save_user(99, "Mimi", "2nd Year")
        schedule = await self.store.create_schedule(
            batch="2nd Year",
            message="Hello",
            send_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
            created_by=1,
        )
        self.assertEqual(len(await self.store.due_schedules()), 1)
        await self.store.record_delivery(schedule["id"], 99, success=True)
        self.assertEqual((await self.store.due_schedules())[0]["sent_to"], [99])
        await self.store.complete_schedule(schedule["id"])
        self.assertEqual(await self.store.list_schedules(), [])

    async def test_invalid_json_is_not_overwritten(self):
        self.store.path.parent.mkdir(parents=True, exist_ok=True)
        self.store.path.write_text("{broken", encoding="utf-8")
        with self.assertRaises(RuntimeError):
            await self.store.health_check()
        self.assertEqual(self.store.path.read_text(encoding="utf-8"), "{broken")


if __name__ == "__main__":
    unittest.main()
