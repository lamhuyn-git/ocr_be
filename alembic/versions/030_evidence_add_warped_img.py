"""evidences: add warped_img column for aligned image S3 path

Revision ID: 030
Revises: 029
Create Date: 2026-06-19
"""
from alembic import op
import sqlalchemy as sa

revision = '030'
down_revision = '029'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('evidences', sa.Column('warped_img', sa.String(512), nullable=True))


def downgrade() -> None:
    op.drop_column('evidences', 'warped_img')
