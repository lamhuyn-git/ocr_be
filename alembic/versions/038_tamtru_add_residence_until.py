from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "038"
down_revision: Union[str, None] = "037"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tamtru_forms",
        sa.Column("residence_until", sa.Date(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tamtru_forms", "residence_until")
