"""add organizations.org_type + seed HCMC wards

Revision ID: 007
Revises: 006
Create Date: 2024-01-07 00:00:00.000000
"""
import re
import uuid
import unicodedata
from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from alembic import op

revision: str = "007"
down_revision: Union[str, None] = "006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Đơn vị hành chính cần seed (tên đầy đủ kèm tiền tố loại đơn vị).
WARDS = [
    "Phường Sài Gòn", "Phường Tân Định", "Phường Bến Thành", "Phường Cầu Ông Lãnh",
    "Phường Bàn Cờ", "Phường Xuân Hòa", "Phường Nhiêu Lộc", "Phường Xóm Chiếu",
    "Phường Khánh Hội", "Phường Vĩnh Hội", "Phường Chợ Quán", "Phường An Đông",
    "Phường Chợ Lớn", "Phường Bình Tây", "Phường Bình Tiên", "Phường Bình Phú",
    "Phường Phú Lâm", "Phường Tân Thuận", "Phường Phú Thuận", "Phường Tân Mỹ",
    "Phường Tân Hưng", "Phường Chánh Hưng", "Phường Phú Định", "Phường Bình Đông",
    "Phường Diên Hồng", "Phường Vườn Lài", "Phường Hòa Hưng", "Phường Minh Phụng",
    "Phường Bình Thới", "Phường Hòa Bình", "Phường Phú Thọ", "Phường Đông Hưng Thuận",
    "Phường Trung Mỹ Tây", "Phường Tân Thới Hiệp", "Phường Thới An", "Phường An Phú Đông",
    "Phường An Lạc", "Phường Bình Tân", "Phường Tân Tạo", "Phường Bình Trị Đông",
    "Phường Bình Hưng Hòa", "Phường Gia Định", "Phường Bình Thạnh", "Phường Bình Lợi Trung",
    "Phường Thạnh Mỹ Tây", "Phường Bình Quới", "Phường Hạnh Thông", "Phường An Nhơn",
    "Phường Gò Vấp", "Phường An Hội Đông", "Phường Thông Tây Hội", "Phường An Hội Tây",
    "Phường Đức Nhuận", "Phường Cầu Kiệu", "Phường Phú Nhuận", "Phường Tân Sơn Hòa",
    "Phường Tân Sơn Nhất", "Phường Tân Hòa", "Phường Bảy Hiền", "Phường Tân Bình",
    "Phường Tân Sơn", "Phường Tây Thạnh", "Phường Tân Sơn Nhì", "Phường Phú Thọ Hòa",
    "Phường Tân Phú", "Phường Phú Thạnh", "Phường Hiệp Bình", "Phường Thủ Đức",
    "Phường Tam Bình", "Phường Linh Xuân", "Phường Tăng Nhơn Phú", "Phường Long Bình",
    "Phường Long Phước", "Phường Long Trường", "Phường Cát Lái", "Phường Bình Trưng",
    "Phường Phước Long", "Phường An Khánh", "Phường Đông Hòa", "Phường Dĩ An",
    "Phường Tân Đông Hiệp", "Phường An Phú", "Phường Bình Hòa", "Phường Lái Thiêu",
    "Phường Thuận An", "Phường Thuận Giao", "Phường Thủ Dầu Một", "Phường Phú Lợi",
    "Phường Chánh Hiệp", "Phường Bình Dương", "Phường Hòa Lợi", "Phường Phú An",
    "Phường Tây Nam", "Phường Long Nguyên", "Phường Bến Cát", "Phường Chánh Phú Hòa",
    "Phường Vĩnh Tân", "Phường Bình Cơ", "Phường Tân Uyên", "Phường Tân Hiệp",
    "Phường Tân Khánh", "Phường Vũng Tàu", "Phường Tam Thắng", "Phường Rạch Dừa",
    "Phường Phước Thắng", "Phường Long Hương", "Phường Bà Rịa", "Phường Tam Long",
    "Phường Tân Hải", "Phường Tân Phước", "Phường Phú Mỹ", "Phường Mỹ Xuân",
    "Phường Thới Hòa", "Đặc khu Côn Đảo",
]


def _slugify(name: str) -> str:
    """Vietnamese-aware slug: bỏ dấu, đ→d, lowercase, nối bằng '-'."""
    s = name.strip().lower().replace("đ", "d")
    s = unicodedata.normalize("NFD", s)
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def _org_type(name: str) -> str:
    n = name.strip().lower()
    if n.startswith("đặc khu") or n.startswith("dac khu"):
        return "dac_khu"
    if n.startswith("xã"):
        return "xa"
    return "phuong"


def upgrade() -> None:
    op.add_column(
        "organizations",
        sa.Column("org_type", sa.String(20), nullable=False, server_default="phuong"),
    )

    org_table = sa.table(
        "organizations",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("slug", sa.String),
        sa.column("org_type", sa.String),
    )

    rows, seen = [], set()
    for name in WARDS:
        slug = _slugify(name)
        if slug in seen:
            continue  # tránh trùng slug (unique)
        seen.add(slug)
        rows.append({"id": uuid.uuid4(), "name": name, "slug": slug, "org_type": _org_type(name)})

    op.bulk_insert(org_table, rows)


def downgrade() -> None:
    slugs = sorted({_slugify(n) for n in WARDS})
    op.execute(
        sa.text("DELETE FROM organizations WHERE slug = ANY(:slugs)").bindparams(slugs=slugs)
    )
    op.drop_column("organizations", "org_type")
