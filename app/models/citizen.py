import enum
import uuid

from sqlalchemy import Column, String, Date, DateTime, Boolean, Enum, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship

from app.database import Base


# ── Enums ───────────────────────────────────────────────────────────────────────

class Gender(str, enum.Enum):
    male = "Nam"
    female = "Nữ"


class MaritalStatus(str, enum.Enum):
    single = "Độc thân"
    married = "Kết hôn"


class ResidenceStatus(str, enum.Enum):
    thuong_tru = "thuong_tru"
    tam_tru = "tam_tru"
    tam_vang = "tam_vang"
    khong_xac_dinh = "khong_xac_dinh"


class LifeStatus(str, enum.Enum):
    alive = "alive"
    dead = "dead"
    missing = "missing"


class RelationType(str, enum.Enum):
    cha = "cha"
    me = "me"
    vo_chong = "vo_chong"
    con = "con"
    chu_ho = "chu_ho"
    anh_chi_em = "anh_chi_em"
    khac = "khac"


# ── Citizen (CSDL quốc gia về dân cư) ─────────────────────────────────────────────

class Citizen(Base):
    """Hồ sơ dân cư — 1:1 với User (User giữ auth, Citizen giữ dữ liệu dân cư).
    Field theo Điều 9 Luật Căn cước 2023; phần lớn nullable vì CSDL điền dần."""
    __tablename__ = "citizens"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Liên kết & định danh
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
                     unique=True, nullable=True, index=True)
    so_dinh_danh = Column(String(12), unique=True, index=True, nullable=False)  # số định danh cá nhân (vĩnh viễn) — khóa CSDL

    # Nhân thân cơ bản
    ho_chu_dem_va_ten = Column(String(255), nullable=False)
    ten_goi_khac = Column(String(255), nullable=True)
    ngay_sinh = Column(Date, nullable=True)
    gioi_tinh = Column(Enum(Gender), nullable=True)
    noi_sinh = Column(String(512), nullable=True)
    noi_dang_ky_khai_sinh = Column(String(512), nullable=True)
    que_quan = Column(String(512), nullable=True)
    dan_toc = Column(String(50), nullable=True)
    ton_giao = Column(String(50), nullable=True)
    quoc_tich = Column(String(50), nullable=True, server_default="Việt Nam")
    nhom_mau = Column(String(5), nullable=True)

    # Cư trú
    noi_thuong_tru = Column(String(512), nullable=True)
    noi_tam_tru = Column(String(512), nullable=True)
    noi_o_hien_tai = Column(String(512), nullable=True)
    tinh_trang_cu_tru = Column(Enum(ResidenceStatus), nullable=True)
    ma_ho = Column(String(20), index=True, nullable=True)
    quan_he_voi_chu_ho = Column(String(50), nullable=True)
    so_dinh_danh_chu_ho = Column(String(12), index=True, nullable=True)

    # Tình trạng
    tinh_trang_hon_nhan = Column(Enum(MaritalStatus), nullable=True)
    nghe_nghiep = Column(String(100), nullable=True)
    tinh_trang_song = Column(Enum(LifeStatus), nullable=True, server_default="alive")
    ngay_mat = Column(Date, nullable=True)

    # Liên hệ
    so_dien_thoai = Column(String(15), nullable=True)
    email = Column(String(255), nullable=True)

    # Trạng thái hồ sơ (kích hoạt sau khi xác minh)
    is_active = Column(Boolean, nullable=False, server_default="false", index=True)

    # (Quan hệ cha/mẹ/vợ-chồng/con lưu ở bảng citizen_relations — không denormalized ở đây.)

    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    user = relationship("User", back_populates="citizen", lazy="noload")
    relations = relationship(
        "CitizenRelation",
        foreign_keys="CitizenRelation.citizen_id",
        back_populates="citizen",
        cascade="all, delete-orphan",
        lazy="noload",
    )


class CitizenRelation(Base):
    """Quan hệ giữa 2 citizen (self-reference) — cha/mẹ/vợ-chồng/con/chủ hộ..."""
    __tablename__ = "citizen_relations"
    __table_args__ = (
        UniqueConstraint("citizen_id", "related_citizen_id", "relation_type", name="uq_citizen_relation"),
    )

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    citizen_id = Column(UUID(as_uuid=True), ForeignKey("citizens.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    related_citizen_id = Column(UUID(as_uuid=True), ForeignKey("citizens.id", ondelete="CASCADE"),
                                nullable=False, index=True)
    relation_type = Column(Enum(RelationType), nullable=False)
    note = Column(String(255), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    citizen = relationship("Citizen", foreign_keys=[citizen_id], back_populates="relations")
    related_citizen = relationship("Citizen", foreign_keys=[related_citizen_id], lazy="noload")
