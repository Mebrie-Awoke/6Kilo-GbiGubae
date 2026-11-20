"""Align Telegram ID columns with the models and remove the incorrect FK.

Revision ID: c7f4a2d91b30
Revises: 8f3a2b1c5d7e
Create Date: 2026-11-20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7f4a2d91b30"
down_revision: Union[str, Sequence[str], None] = "8f3a2b1c5d7e"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Telegram user IDs are 64-bit values; the original schema used INTEGER.
    op.alter_column(
        "users",
        "user_id",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
        postgresql_using="user_id::bigint",
    )

    # admin_id stores a Telegram user ID in the current model and write path.
    # The original migration incorrectly declared it as an FK to users.id.
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    admin_id_was_foreign_key = False
    for foreign_key in inspector.get_foreign_keys("schedules"):
        if foreign_key.get("constrained_columns") == ["admin_id"]:
            op.drop_constraint(
                foreign_key["name"],
                "schedules",
                type_="foreignkey",
            )
            admin_id_was_foreign_key = True

    # Existing rows constrained by the original FK stored users.id. Convert
    # those values to Telegram IDs. If no FK existed, leave existing values
    # untouched because they may already be Telegram IDs.
    if admin_id_was_foreign_key:
        op.execute(
            sa.text(
                "UPDATE schedules AS s "
                "SET admin_id = u.user_id "
                "FROM users AS u "
                "WHERE s.admin_id = u.id"
            )
        )


def downgrade() -> None:
    # The old FK is intentionally not recreated: admin_id contains Telegram
    # IDs, not necessarily internal users.id values.
    op.alter_column(
        "users",
        "user_id",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
        postgresql_using="user_id::integer",
    )
