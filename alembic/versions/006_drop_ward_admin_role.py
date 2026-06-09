"""collapse orgrole to a single ward_officer value (drop ward_admin)

Revision ID: 006
Revises: 005
Create Date: 2024-01-06 00:00:00.000000

3-tier role model: super_admin (users.is_superuser) / ward_officer (membership) / citizen.
Existing ward_admin memberships are remapped to ward_officer.
"""
from typing import Sequence, Union
from alembic import op

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("ALTER TABLE organization_members ALTER COLUMN role DROP DEFAULT")
    op.execute("CREATE TYPE orgrole_new AS ENUM ('ward_officer')")
    op.execute(
        "ALTER TABLE organization_members ALTER COLUMN role TYPE orgrole_new "
        "USING ('ward_officer')::orgrole_new"
    )
    op.execute("DROP TYPE orgrole")
    op.execute("ALTER TYPE orgrole_new RENAME TO orgrole")
    op.execute("ALTER TABLE organization_members ALTER COLUMN role SET DEFAULT 'ward_officer'")


def downgrade() -> None:
    # Forward-only: the ward_admin distinction is gone and cannot be reconstructed.
    raise NotImplementedError(
        "Migration 006 is forward-only: ward_admin was collapsed into ward_officer."
    )
