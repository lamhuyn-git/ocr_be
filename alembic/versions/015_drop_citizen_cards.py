"""drop citizen_cards (ngoài scope hiện tại)

Revision ID: 015
Revises: 014
Create Date: 2024-01-15 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "015"
down_revision: Union[str, None] = "014"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID
CARDTYPE = postgresql.ENUM("cmnd_9", "cccd", "cccd_chip", name="cardtype", create_type=False)
CARDSTATUS = postgresql.ENUM("active", "expired", "replaced", "lost", "revoked", name="cardstatus", create_type=False)


def upgrade() -> None:
    op.drop_table("citizen_cards")
    bind = op.get_bind()
    for e in (CARDTYPE, CARDSTATUS):
        e.drop(bind, checkfirst=True)


def downgrade() -> None:
    bind = op.get_bind()
    for e in (CARDTYPE, CARDSTATUS):
        e.create(bind, checkfirst=True)
    op.create_table(
        "citizen_cards",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("citizen_id", UUID(as_uuid=True), sa.ForeignKey("citizens.id", ondelete="CASCADE"), nullable=False),
        sa.Column("card_type", CARDTYPE, nullable=False),
        sa.Column("card_number", sa.String(12), nullable=False),
        sa.Column("ngay_cap", sa.Date(), nullable=True),
        sa.Column("noi_cap", sa.String(255), nullable=True),
        sa.Column("ngay_het_han", sa.Date(), nullable=True),
        sa.Column("status", CARDSTATUS, server_default="active", nullable=False),
        sa.Column("is_current", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_citizen_cards_citizen_id", "citizen_cards", ["citizen_id"])
    op.create_index("ix_citizen_cards_card_number", "citizen_cards", ["card_number"])
    op.create_index("ix_citizen_cards_is_current", "citizen_cards", ["is_current"])
