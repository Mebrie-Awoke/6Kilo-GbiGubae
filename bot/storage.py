"""Small atomic JSON storage. Run one bot instance against one data file."""
import asyncio
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _empty_data() -> dict[str, Any]:
    return {"users": {}, "schedules": [], "next_schedule_id": 1}


class JsonStore:
    def __init__(self, file_path: str | Path):
        self.path = Path(file_path)
        self._lock = asyncio.Lock()

    def _read_sync(self) -> dict[str, Any]:
        if not self.path.exists():
            return _empty_data()
        try:
            with self.path.open("r", encoding="utf-8") as file:
                data = json.load(file)
        except json.JSONDecodeError as exc:
            raise RuntimeError(
                f"Storage file {self.path} contains invalid JSON. Restore a backup; it was not overwritten."
            ) from exc
        if not isinstance(data, dict):
            raise RuntimeError("Storage file has an invalid top-level structure.")
        data.setdefault("users", {})
        data.setdefault("schedules", [])
        data.setdefault("next_schedule_id", 1)
        return data

    def _write_sync(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        with temporary.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temporary, self.path)

    async def _read(self) -> dict[str, Any]:
        return await asyncio.to_thread(self._read_sync)

    async def _write(self, data: dict[str, Any]) -> None:
        await asyncio.to_thread(self._write_sync, data)

    async def health_check(self) -> bool:
        async with self._lock:
            data = await self._read()
            await self._write(data)
        return True

    async def save_user(self, user_id: int, name: str, batch: str) -> None:
        async with self._lock:
            data = await self._read()
            data["users"][str(user_id)] = {"name": name.strip(), "batch": batch}
            await self._write(data)

    async def get_user(self, user_id: int) -> dict[str, Any] | None:
        async with self._lock:
            data = await self._read()
            user = data["users"].get(str(user_id))
            return deepcopy(user) if user else None

    async def list_users(self, batch: str | None = None) -> list[dict[str, Any]]:
        async with self._lock:
            data = await self._read()
            result = []
            for telegram_id, user in data["users"].items():
                if batch is None or user.get("batch") == batch:
                    result.append({
                        "telegram_id": int(telegram_id),
                        "name": user.get("name", ""),
                        "batch": user.get("batch", ""),
                    })
            return result

    async def create_schedule(
        self, *, batch: str, message: str, send_at: datetime, created_by: int
    ) -> dict[str, Any]:
        async with self._lock:
            data = await self._read()
            schedule = {
                "id": int(data["next_schedule_id"]),
                "batch": batch,
                "message": message,
                "send_at": send_at.astimezone(timezone.utc).isoformat(),
                "created_by": created_by,
                "status": "pending",
                "sent_to": [],
                "failed_to": [],
            }
            data["next_schedule_id"] = schedule["id"] + 1
            data["schedules"].append(schedule)
            await self._write(data)
            return deepcopy(schedule)

    async def list_schedules(self, include_completed: bool = False) -> list[dict[str, Any]]:
        async with self._lock:
            data = await self._read()
            schedules = data["schedules"]
            if not include_completed:
                schedules = [item for item in schedules if item.get("status") == "pending"]
            return deepcopy(sorted(schedules, key=lambda item: item["send_at"]))

    async def cancel_schedule(self, schedule_id: int) -> bool:
        async with self._lock:
            data = await self._read()
            for schedule in data["schedules"]:
                if schedule["id"] == schedule_id and schedule["status"] == "pending":
                    schedule["status"] = "cancelled"
                    await self._write(data)
                    return True
            return False

    async def due_schedules(self, now: datetime | None = None) -> list[dict[str, Any]]:
        now = now or datetime.now(timezone.utc)
        async with self._lock:
            data = await self._read()
            due = []
            for schedule in data["schedules"]:
                if schedule.get("status") != "pending":
                    continue
                if datetime.fromisoformat(schedule["send_at"]) <= now:
                    due.append(deepcopy(schedule))
            return due

    async def record_delivery(self, schedule_id: int, user_id: int, success: bool) -> None:
        async with self._lock:
            data = await self._read()
            for schedule in data["schedules"]:
                if schedule["id"] == schedule_id:
                    key = "sent_to" if success else "failed_to"
                    if user_id not in schedule[key]:
                        schedule[key].append(user_id)
                    await self._write(data)
                    return

    async def complete_schedule(self, schedule_id: int) -> None:
        async with self._lock:
            data = await self._read()
            for schedule in data["schedules"]:
                if schedule["id"] == schedule_id:
                    schedule["status"] = "completed"
                    schedule["completed_at"] = datetime.now(timezone.utc).isoformat()
                    await self._write(data)
                    return

    async def fail_schedule(self, schedule_id: int, error: str) -> None:
        async with self._lock:
            data = await self._read()
            for schedule in data["schedules"]:
                if schedule["id"] == schedule_id:
                    schedule["last_error"] = error[:500]
                    await self._write(data)
                    return
