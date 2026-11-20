# db/models.py — ULTIMATE VERSION
from sqlalchemy import (
    Column, Integer, String, Boolean, DateTime, ForeignKey, Enum, Table, Text,
    JSON, BigInteger, UniqueConstraint, Index
)
from sqlalchemy.dialects.postgresql import BIGINT
from sqlalchemy.orm import relationship, declarative_base
from datetime import datetime
import enum

Base = declarative_base()

class ScheduleType(enum.Enum):
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    CUSTOM = "custom"

schedule_batch_association = Table(
    "schedule_batch_association",
    Base.metadata,
    Column("schedule_id", ForeignKey("schedules.id"), primary_key=True),
    Column("batch_id", ForeignKey("batches.id"), primary_key=True)
)

class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)  # Internal DB ID
    user_id = Column(BIGINT, unique=True, nullable=False)  # Telegram ID
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    gender = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)
    batch_id = Column(Integer, ForeignKey("batches.id"), nullable=True)
    join_date = Column(DateTime, default=datetime.utcnow)
    batch = relationship("Batch", back_populates="users")

class Batch(Base):
    __tablename__ = "batches"
    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)
    users = relationship("User", back_populates="batch")
    schedules = relationship(
        "Schedule",
        secondary=schedule_batch_association,
        back_populates="batches"
    )

class Schedule(Base):
    __tablename__ = "schedules"
    id = Column(Integer, primary_key=True)
    message = Column(Text, nullable=True)  # Now optional (can be media-only)
    media_type = Column(String, nullable=True)  # 'photo', 'video', 'document', or None
    media_file_id = Column(String, nullable=True)  # Telegram file_id
    caption = Column(Text, nullable=True)  # Caption for media (optional)
    type = Column(Enum(ScheduleType), nullable=False)
    cron_expr = Column(String, nullable=True)      # e.g., "0 9 * * 1"
    next_run = Column(DateTime, nullable=True)     # When to send next
    created_at = Column(DateTime, default=datetime.utcnow)
    admin_id = Column(BIGINT, nullable=False)      # ← Telegram ID
    is_active = Column(Boolean, default=True)
    batches = relationship(
        "Batch",
        secondary=schedule_batch_association,
        back_populates="schedules"
    )


class TelegramUpdate(Base):
    """Durable inbox for Telegram webhook updates."""
    __tablename__ = "telegram_updates"

    update_id = Column(BigInteger, primary_key=True)
    payload = Column(JSON, nullable=False)
    status = Column(String(20), nullable=False, default="pending", index=True)
    attempts = Column(Integer, nullable=False, default=0)
    received_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    locked_at = Column(DateTime, nullable=True)
    processed_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)


class FSMState(Base):
    """Persistent Aiogram conversation state and data."""
    __tablename__ = "fsm_states"

    key = Column(String(255), primary_key=True)
    state = Column(String(255), nullable=True)
    data = Column(JSON, nullable=False, default=dict)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow)


class BroadcastRun(Base):
    """One occurrence of a recurring schedule."""
    __tablename__ = "broadcast_runs"
    __table_args__ = (
        UniqueConstraint(
            "schedule_id", "scheduled_for",
            name="uq_broadcast_run_schedule_occurrence",
        ),
        Index("ix_broadcast_runs_status", "status"),
    )

    id = Column(Integer, primary_key=True)
    schedule_id = Column(
        Integer, ForeignKey("schedules.id", ondelete="CASCADE"), nullable=False
    )
    scheduled_for = Column(DateTime, nullable=False)
    status = Column(String(30), nullable=False, default="pending")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)


class BroadcastDelivery(Base):
    """Persistent per-user delivery record; survives worker restarts."""
    __tablename__ = "broadcast_deliveries"
    __table_args__ = (
        UniqueConstraint("run_id", "user_id", name="uq_broadcast_delivery_recipient"),
        Index("ix_broadcast_deliveries_status", "status"),
    )

    id = Column(Integer, primary_key=True)
    run_id = Column(
        Integer, ForeignKey("broadcast_runs.id", ondelete="CASCADE"), nullable=False
    )
    user_id = Column(BigInteger, nullable=False)
    full_name = Column(String, nullable=True)
    message = Column(Text, nullable=True)
    media_type = Column(String, nullable=True)
    media_file_id = Column(String, nullable=True)
    status = Column(String(20), nullable=False, default="pending")
    attempts = Column(Integer, nullable=False, default=0)
    locked_at = Column(DateTime, nullable=True)
    sent_at = Column(DateTime, nullable=True)
    last_error = Column(Text, nullable=True)
