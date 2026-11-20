"""PostgreSQL-backed Aiogram FSM storage."""
from datetime import datetime

from aiogram.fsm.storage.base import BaseStorage, StorageKey
from sqlalchemy.dialects.postgresql import insert

from db.models import FSMState
from db.session import AsyncSessionLocal
from storage.json_codec import decode_fsm_value, encode_fsm_value


class PostgresStorage(BaseStorage):
    """Persist conversation state so Render restarts do not reset user flows."""

    @staticmethod
    def _key(key: StorageKey) -> str:
        return ":".join(
            str(value or "-")
            for value in (
                key.bot_id,
                key.chat_id,
                key.user_id,
                key.thread_id,
                key.business_connection_id,
                key.destiny,
            )
        )

    async def set_state(self, key: StorageKey, state: str | None = None) -> None:
        state_value = getattr(state, "state", state)
        storage_key = self._key(key)
        now = datetime.utcnow()
        statement = insert(FSMState).values(
            key=storage_key,
            state=state_value,
            data={},
            updated_at=now,
        ).on_conflict_do_update(
            index_elements=[FSMState.key],
            set_={"state": state_value, "updated_at": now},
        )
        async with AsyncSessionLocal() as session:
            await session.execute(statement)
            await session.commit()

    async def get_state(self, key: StorageKey) -> str | None:
        async with AsyncSessionLocal() as session:
            row = await session.get(FSMState, self._key(key))
            return row.state if row else None

    async def set_data(self, key: StorageKey, data: dict) -> None:
        storage_key = self._key(key)
        now = datetime.utcnow()
        safe_data = encode_fsm_value(dict(data or {}))
        statement = insert(FSMState).values(
            key=storage_key,
            state=None,
            data=safe_data,
            updated_at=now,
        ).on_conflict_do_update(
            index_elements=[FSMState.key],
            set_={"data": safe_data, "updated_at": now},
        )
        async with AsyncSessionLocal() as session:
            await session.execute(statement)
            await session.commit()

    async def get_data(self, key: StorageKey) -> dict:
        async with AsyncSessionLocal() as session:
            row = await session.get(FSMState, self._key(key))
            return decode_fsm_value(dict(row.data or {})) if row else {}

    async def close(self) -> None:
        # The shared SQLAlchemy engine is disposed by the application lifecycle.
        return None
