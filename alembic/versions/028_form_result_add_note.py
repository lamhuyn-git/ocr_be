"""form_results: add note column for verdict reason

Revision ID: 028
Revises: 027
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa

revision = '028'
down_revision = '027'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('form_results', sa.Column('note', sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column('form_results', 'note')
