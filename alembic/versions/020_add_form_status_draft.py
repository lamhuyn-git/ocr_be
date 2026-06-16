"""add 'draft' value to formstatus enum

Revision ID: 020
Revises: 019
Create Date: 2026-06-16 00:00:00.000000

Recreate enum (an toàn với asyncpg, tránh ALTER TYPE ADD VALUE trong transaction).
"""
from typing import Sequence, Union

from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_VALUES = "'draft','submitted','processing','extracted','under_review','approved','rejected','returned','failed'"


def upgrade() -> None:
    op.execute("ALTER TABLE forms ALTER COLUMN status DROP DEFAULT")
    op.execute(f"CREATE TYPE formstatus_new AS ENUM ({_VALUES})")
    op.execute("ALTER TABLE forms ALTER COLUMN status TYPE formstatus_new USING status::text::formstatus_new")
    op.execute("DROP TYPE formstatus")
    op.execute("ALTER TYPE formstatus_new RENAME TO formstatus")
    op.execute("ALTER TABLE forms ALTER COLUMN status SET DEFAULT 'submitted'")


def downgrade() -> None:
    raise NotImplementedError("Migration 020 is forward-only (added 'draft' to formstatus).")
