"""Add durable Telegram updates, FSM state, and broadcast deliveries.

Revision ID: e13a9d7c4b20
Revises: c7f4a2d91b30
Create Date: 2026-11-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e13a9d7c4b20"
down_revision: Union[str, Sequence[str], None] = "c7f4a2d91b30"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_updates",
        sa.Column("update_id", sa.BigInteger(), primary_key=True),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("received_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
    )
    op.create_index("ix_telegram_updates_status", "telegram_updates", ["status"])

    op.create_table(
        "fsm_states",
        sa.Column("key", sa.String(length=255), primary_key=True),
        sa.Column("state", sa.String(length=255), nullable=True),
        sa.Column("data", sa.JSON(), nullable=False, server_default=sa.text("'{}'")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "broadcast_runs",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "schedule_id",
            sa.Integer(),
            sa.ForeignKey("schedules.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scheduled_for", sa.DateTime(), nullable=False),
        sa.Column("status", sa.String(length=30), nullable=False, server_default="pending"),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.UniqueConstraint(
            "schedule_id",
            "scheduled_for",
            name="uq_broadcast_run_schedule_occurrence",
        ),
    )
    op.create_index("ix_broadcast_runs_status", "broadcast_runs", ["status"])

    op.create_table(
        "broadcast_deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "run_id",
            sa.Integer(),
            sa.ForeignKey("broadcast_runs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("user_id", sa.BigInteger(), nullable=False),
        sa.Column("full_name", sa.String(), nullable=True),
        sa.Column("message", sa.Text(), nullable=True),
        sa.Column("media_type", sa.String(), nullable=True),
        sa.Column("media_file_id", sa.String(), nullable=True),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("locked_at", sa.DateTime(), nullable=True),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.UniqueConstraint(
            "run_id",
            "user_id",
            name="uq_broadcast_delivery_recipient",
        ),
    )
    op.create_index(
        "ix_broadcast_deliveries_status",
        "broadcast_deliveries",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("ix_broadcast_deliveries_status", table_name="broadcast_deliveries")
    op.drop_table("broadcast_deliveries")
    op.drop_index("ix_broadcast_runs_status", table_name="broadcast_runs")
    op.drop_table("broadcast_runs")
    op.drop_table("fsm_states")
    op.drop_index("ix_telegram_updates_status", table_name="telegram_updates")
    op.drop_table("telegram_updates")
