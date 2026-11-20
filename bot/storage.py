"""MongoDB persistence for members and scheduled announcements."""
from datetime import datetime, timezone
from typing import Any

from pymongo import ASCENDING, DESCENDING, ReturnDocument
from pymongo import AsyncMongoClient


class MongoStore:
    def __init__(self, uri: str, database_name: str):
        self.client = AsyncMongoClient(
            uri,
            serverSelectionTimeoutMS=5000,
            tz_aware=True,
        )
        self.db = self.client[database_name]
        self.users = self.db["users"]
        self.schedules = self.db["schedules"]
        self.counters = self.db["counters"]

    async def connect(self) -> None:
        await self.client.admin.command("ping")
        await self.users.create_index([("batch", ASCENDING)])
        await self.schedules.create_index([("status", ASCENDING), ("send_at", ASCENDING)])
        await self.counters.update_one(
            {"_id": "schedule_id"},
            {"$setOnInsert": {"value": 0}},
            upsert=True,
        )

    async def close(self) -> None:
        await self.client.close()

    async def health_check(self) -> bool:
        await self.client.admin.command("ping")
        return True

    async def save_user(self, user_id: int, name: str, batch: str) -> None:
        await self.users.update_one(
            {"_id": int(user_id)},
            {"$set": {"name": name.strip(), "batch": batch}},
            upsert=True,
        )

    async def get_user(self, user_id: int) -> dict[str, Any] | None:
        user = await self.users.find_one({"_id": int(user_id)})
        if not user:
            return None
        return {"name": user.get("name", ""), "batch": user.get("batch", "")}

    async def list_users(self, batch: str | None = None) -> list[dict[str, Any]]:
        query = {"batch": batch} if batch is not None else {}
        cursor = self.users.find(query).sort("_id", ASCENDING)
        result = []
        async for user in cursor:
            result.append({
                "telegram_id": int(user["_id"]),
                "name": user.get("name", ""),
                "batch": user.get("batch", ""),
            })
        return result

    async def create_schedule(
        self, *, batch: str, message: str, send_at: datetime, created_by: int
    ) -> dict[str, Any]:
        counter = await self.counters.find_one_and_update(
            {"_id": "schedule_id"},
            {"$inc": {"value": 1}},
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        schedule_id = int(counter["value"])
        schedule = {
            "_id": schedule_id,
            "batch": batch,
            "message": message,
            "send_at": send_at.astimezone(timezone.utc),
            "created_by": int(created_by),
            "status": "pending",
            "sent_to": [],
            "failed_to": [],
        }
        await self.schedules.insert_one(schedule)
        return self._format_schedule(schedule)

    @staticmethod
    def _format_schedule(item: dict[str, Any]) -> dict[str, Any]:
        send_at = item["send_at"]
        if isinstance(send_at, datetime):
            send_at = send_at.astimezone(timezone.utc).isoformat()
        result = {key: value for key, value in item.items() if key != "_id"}
        result["id"] = int(item["_id"])
        result["send_at"] = send_at
        return result

    async def list_schedules(self, include_completed: bool = False) -> list[dict[str, Any]]:
        query = {} if include_completed else {"status": "pending"}
        cursor = self.schedules.find(query).sort("send_at", ASCENDING)
        return [self._format_schedule(item) async for item in cursor]

    async def cancel_schedule(self, schedule_id: int) -> bool:
        result = await self.schedules.update_one(
            {"_id": int(schedule_id), "status": "pending"},
            {"$set": {"status": "cancelled"}},
        )
        return result.modified_count > 0

    async def due_schedules(self, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or datetime.now(timezone.utc)
        cursor = self.schedules.find({"status": "pending", "send_at": {"$lte": now}})
        return [self._format_schedule(item) async for item in cursor]

    async def record_delivery(self, schedule_id: int, user_id: int, success: bool) -> None:
        field = "sent_to" if success else "failed_to"
        await self.schedules.update_one(
            {"_id": int(schedule_id)},
            {"$addToSet": {field: int(user_id)}},
        )

    async def complete_schedule(self, schedule_id: int) -> None:
        await self.schedules.update_one(
            {"_id": int(schedule_id)},
            {"$set": {
                "status": "completed",
                "completed_at": datetime.now(timezone.utc),
            }},
        )

    async def fail_schedule(self, schedule_id: int, error: str) -> None:
        await self.schedules.update_one(
            {"_id": int(schedule_id)},
            {"$set": {"last_error": error[:500]}},
        )
