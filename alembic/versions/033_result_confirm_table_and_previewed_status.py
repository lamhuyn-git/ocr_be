"""add result_confirm table, previewed formstatus; drop final_value/confirmed_by from form_results

Revision ID: 033
Revises: 032
Create Date: 2026-06-23 23:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "033"
down_revision: Union[str, None] = "032"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_FORMSTATUS_NEW = (
    "'draft','submitted','processing','extracted','under_review','previewed','reviewed',"
    "'returned','failed','overdue','gate_rejected'"
)


def upgrade() -> None:
    # 1. Drop final_value and confirmed_by from form_results
    op.drop_column("form_results", "final_value")
    op.drop_column("form_results", "confirmed_by")

    # 2. Add 'previewed' to formstatus enum (recreate pattern used throughout this project)
    op.execute("ALTER TABLE forms ALTER COLUMN status DROP DEFAULT")
    op.execute(f"CREATE TYPE formstatus_new AS ENUM ({_FORMSTATUS_NEW})")
    op.execute(
        "ALTER TABLE forms ALTER COLUMN status TYPE formstatus_new "
        "USING status::text::formstatus_new"
    )
    op.execute("DROP TYPE formstatus")
    op.execute("ALTER TYPE formstatus_new RENAME TO formstatus")
    op.execute("ALTER TABLE forms ALTER COLUMN status SET DEFAULT 'submitted'")

    # 3 + 4. Create resultconfirmstatus enum + result_confirm table via raw SQL
    # (avoids SQLAlchemy re-creating the enum automatically during op.create_table)
    op.execute("CREATE TYPE resultconfirmstatus AS ENUM ('valid', 'invalid')")
    op.execute("""
        CREATE TABLE result_confirm (
            id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
            checkpoint_id UUID NOT NULL REFERENCES form_results(id) ON DELETE CASCADE,
            confirmed_by UUID,
            final_status resultconfirmstatus NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
    """)
    op.execute(
        "CREATE INDEX ix_result_confirm_checkpoint_id ON result_confirm (checkpoint_id)"
    )


def downgrade() -> None:
    raise NotImplementedError("Migration 033 is forward-only.")
