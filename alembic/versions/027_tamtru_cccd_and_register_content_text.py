"""tamtru: replace registered_user_id with registered_user_cccd, register_content JSONB → Text

Revision ID: 027
Revises: 026
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '027'
down_revision = '026'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Xóa FK constraint + column registered_user_id, thêm registered_user_cccd (String 12)
    op.drop_constraint('tamtru_forms_registered_user_id_fkey', 'tamtru_forms', type_='foreignkey')
    op.drop_column('tamtru_forms', 'registered_user_id')
    op.add_column('tamtru_forms', sa.Column('registered_user_cccd', sa.String(12), nullable=True))

    # Đổi register_content từ JSONB → Text (cast sang text)
    op.alter_column(
        'tamtru_forms', 'register_content',
        existing_type=postgresql.JSONB(),
        type_=sa.Text(),
        postgresql_using='register_content::text',
    )


def downgrade() -> None:
    # Đổi register_content Text → JSONB
    op.alter_column(
        'tamtru_forms', 'register_content',
        existing_type=sa.Text(),
        type_=postgresql.JSONB(),
        postgresql_using='register_content::jsonb',
    )

    # Xóa registered_user_cccd, thêm lại registered_user_id
    op.drop_column('tamtru_forms', 'registered_user_cccd')
    op.add_column('tamtru_forms', sa.Column(
        'registered_user_id', postgresql.UUID(as_uuid=True), nullable=True,
    ))
    op.create_foreign_key(
        'tamtru_forms_registered_user_id_fkey',
        'tamtru_forms', 'users',
        ['registered_user_id'], ['id'],
        ondelete='SET NULL',
    )
