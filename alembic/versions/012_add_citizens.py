"""add citizens + citizen_relations (CSDL quốc gia về dân cư)

Revision ID: 012
Revises: 011
Create Date: 2024-01-12 00:00:00.000000
"""
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "012"
down_revision: Union[str, None] = "011"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

UUID = postgresql.UUID

# Enum types (tên khớp default SQLAlchemy = lowercase tên class python).
# create_type=False: tự tạo thủ công bằng .create() bên dưới; create_table KHÔNG tự emit CREATE TYPE.
GENDER = postgresql.ENUM("male", "female", "other", name="gender", create_type=False)
MARITAL = postgresql.ENUM("single", "married", "divorced", "widowed", name="maritalstatus", create_type=False)
RESIDENCE = postgresql.ENUM("thuong_tru", "tam_tru", "tam_vang", "khong_xac_dinh", name="residencestatus", create_type=False)
LIFE = postgresql.ENUM("alive", "dead", "missing", name="lifestatus", create_type=False)
RELATION = postgresql.ENUM("cha", "me", "vo_chong", "con", "chu_ho", "anh_chi_em", "khac", name="relationtype", create_type=False)
CARDTYPE = postgresql.ENUM("cmnd_9", "cccd", "cccd_chip", name="cardtype", create_type=False)
CARDSTATUS = postgresql.ENUM("active", "expired", "replaced", "lost", "revoked", name="cardstatus", create_type=False)


def upgrade() -> None:
    bind = op.get_bind()
    for e in (GENDER, MARITAL, RESIDENCE, LIFE, RELATION, CARDTYPE, CARDSTATUS):
        e.create(bind, checkfirst=True)

    op.create_table(
        "citizens",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        # Liên kết & định danh
        sa.Column("user_id", UUID(as_uuid=True), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("so_dinh_danh", sa.String(12), nullable=False),
        # Nhân thân
        sa.Column("ho_chu_dem_va_ten", sa.String(255), nullable=False),
        sa.Column("ten_goi_khac", sa.String(255), nullable=True),
        sa.Column("ngay_sinh", sa.Date(), nullable=True),
        sa.Column("gioi_tinh", GENDER, nullable=True),
        sa.Column("noi_sinh", sa.String(512), nullable=True),
        sa.Column("noi_dang_ky_khai_sinh", sa.String(512), nullable=True),
        sa.Column("que_quan", sa.String(512), nullable=True),
        sa.Column("dan_toc", sa.String(50), nullable=True),
        sa.Column("ton_giao", sa.String(50), nullable=True),
        sa.Column("quoc_tich", sa.String(50), server_default="Việt Nam", nullable=True),
        sa.Column("nhom_mau", sa.String(5), nullable=True),
        # Cư trú
        sa.Column("noi_thuong_tru", sa.String(512), nullable=True),
        sa.Column("noi_tam_tru", sa.String(512), nullable=True),
        sa.Column("noi_o_hien_tai", sa.String(512), nullable=True),
        sa.Column("tinh_trang_cu_tru", RESIDENCE, nullable=True),
        sa.Column("ma_ho", sa.String(20), nullable=True),
        sa.Column("quan_he_voi_chu_ho", sa.String(50), nullable=True),
        sa.Column("so_dinh_danh_chu_ho", sa.String(12), nullable=True),
        # Tình trạng
        sa.Column("tinh_trang_hon_nhan", MARITAL, nullable=True),
        sa.Column("nghe_nghiep", sa.String(100), nullable=True),
        sa.Column("tinh_trang_song", LIFE, server_default="alive", nullable=True),
        sa.Column("ngay_mat", sa.Date(), nullable=True),
        # Liên hệ
        sa.Column("so_dien_thoai", sa.String(15), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        # Audit
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_citizens_user_id", "citizens", ["user_id"], unique=True)
    op.create_index("ix_citizens_so_dinh_danh", "citizens", ["so_dinh_danh"], unique=True)
    op.create_index("ix_citizens_ma_ho", "citizens", ["ma_ho"])
    op.create_index("ix_citizens_so_dinh_danh_chu_ho", "citizens", ["so_dinh_danh_chu_ho"])

    op.create_table(
        "citizen_relations",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("citizen_id", UUID(as_uuid=True), sa.ForeignKey("citizens.id", ondelete="CASCADE"), nullable=False),
        sa.Column("related_citizen_id", UUID(as_uuid=True), sa.ForeignKey("citizens.id", ondelete="CASCADE"), nullable=False),
        sa.Column("relation_type", RELATION, nullable=False),
        sa.Column("note", sa.String(255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("citizen_id", "related_citizen_id", "relation_type", name="uq_citizen_relation"),
    )
    op.create_index("ix_citizen_relations_citizen_id", "citizen_relations", ["citizen_id"])
    op.create_index("ix_citizen_relations_related_citizen_id", "citizen_relations", ["related_citizen_id"])

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


def downgrade() -> None:
    op.drop_table("citizen_cards")
    op.drop_table("citizen_relations")
    op.drop_table("citizens")
    bind = op.get_bind()
    for e in (CARDSTATUS, CARDTYPE, RELATION, LIFE, RESIDENCE, MARITAL, GENDER):
        e.drop(bind, checkfirst=True)
