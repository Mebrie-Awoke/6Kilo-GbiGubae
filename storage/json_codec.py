"""Safe JSON encoding for values used by Aiogram FSM contexts."""
from datetime import date, datetime
from enum import Enum
from typing import Any

from db.models import ScheduleType


def encode_fsm_value(value: Any) -> Any:
    if isinstance(value, datetime):
        return {"__fsm_type__": "datetime", "value": value.isoformat()}
    if isinstance(value, date):
        return {"__fsm_type__": "date", "value": value.isoformat()}
    if isinstance(value, ScheduleType):
        return {"__fsm_type__": "schedule_type", "value": value.name}
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, dict):
        return {str(key): encode_fsm_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [encode_fsm_value(item) for item in value]
    return value


def decode_fsm_value(value: Any) -> Any:
    if isinstance(value, list):
        return [decode_fsm_value(item) for item in value]
    if isinstance(value, dict):
        kind = value.get("__fsm_type__")
        raw = value.get("value")
        if kind == "datetime":
            return datetime.fromisoformat(raw)
        if kind == "date":
            return date.fromisoformat(raw)
        if kind == "schedule_type":
            return ScheduleType[raw]
        return {key: decode_fsm_value(item) for key, item in value.items()}
    return value
