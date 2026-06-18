"""form_results: change position from Integer to JSONB [x, y, w, h]

Revision ID: 029
Revises: 028
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB

revision = '029'
down_revision = '028'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_column('form_results', 'position')
    op.add_column('form_results', sa.Column('position', JSONB(), nullable=True))


def downgrade() -> None:
    op.drop_column('form_results', 'position')
    op.add_column('form_results', sa.Column('position', sa.Integer(), nullable=True, server_default='0'))
