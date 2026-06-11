"""drop legacy ocr_jobs table + jobstatus enum

Revision ID: 009
Revises: 008
Create Date: 2024-01-09 00:00:00.000000

The generic OCR-job flow is superseded by the structured `forms` pipeline.
"""
from typing import Sequence, Union

from alembic import op

revision: str = "009"
down_revision: Union[str, None] = "008"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("ocr_jobs")
    op.execute("DROP TYPE IF EXISTS jobstatus")


def downgrade() -> None:
    # Forward-only: the legacy ocr_jobs table/flow has been removed and is not restored.
    raise NotImplementedError("Migration 009 is forward-only: ocr_jobs was dropped.")
