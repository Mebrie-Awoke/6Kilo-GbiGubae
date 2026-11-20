import unittest
from unittest.mock import AsyncMock, MagicMock

from bot.storage import MongoStore


class MongoStoreTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.store = MongoStore("mongodb://localhost:27017", "test")
        self.store.users = MagicMock()
        self.store.users.update_one = AsyncMock()
        self.store.users.find_one = AsyncMock(return_value={
            "_id": 12345, "name": "Abebe", "batch": "1st Year"
        })
        self.store.locks = MagicMock()
        self.store.locks.find_one_and_update = AsyncMock(return_value={"_id": "scheduler"})
        self.store.locks.update_one = AsyncMock(return_value=MagicMock(modified_count=1))

    async def test_scheduler_lock_acquire(self):
        self.assertTrue(await self.store.acquire_scheduler_lock("worker-a"))
        self.store.locks.find_one_and_update.assert_awaited_once()

    async def test_scheduler_lock_renewal(self):
        self.assertTrue(await self.store.renew_scheduler_lock("worker-a"))
        self.store.locks.update_one.assert_awaited_once()

    async def test_scheduler_lock_release(self):
        await self.store.release_scheduler_lock("worker-a")
        self.store.locks.update_one.assert_awaited_once()

    async def test_save_user_uses_telegram_id_as_document_id(self):
        await self.store.save_user(12345, " Abebe ", "1st Year")
        self.store.users.update_one.assert_awaited_once_with(
            {"_id": 12345},
            {"$set": {"name": "Abebe", "batch": "1st Year"}},
            upsert=True,
        )

    async def test_get_user_returns_public_member_fields(self):
        self.assertEqual(
            await self.store.get_user(12345),
            {"name": "Abebe", "batch": "1st Year"},
        )


if __name__ == "__main__":
    unittest.main()
