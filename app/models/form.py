from __future__ import annotations
import uuid
import enum
from sqlalchemy import (
    Column, String, DateTime, Date, Boolean, Enum, Text, ForeignKey,
)
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base


class FormStatus(str, enum.Enum):
    draft          = "draft"           # nháp, chưa nộp
    submitted      = "submitted"       # Đã tiếp nhận — người dân vừa nộp xong
    processing     = "processing"      # Đang trích xuất — OCR đang chạy, đối chiếu dữ liệu
    extracted      = "extracted"       # Đã trích xuất — AI xong, chờ kiểm tra viên
    under_review   = "under_review"    # Đang xem xét — kiểm tra viên đang xử lý (khóa hồ sơ)
    reviewed       = "reviewed"        # Đã xem — cán bộ đã soát/lưu, chờ trả kết quả
    returned       = "returned"        # Đã trả kết quả cho người dân (xác nhận cuối sau reviewed)
    failed         = "failed"          # Lỗi — hồ sơ bị lỗi trích xuất
    overdue        = "overdue"         # Quá hạn — quá 7 ngày chưa xử lý
    gate_rejected  = "gate_rejected"   # Bị chặn ở cổng kiểm tra (định danh/địa chỉ/sai người) — chưa cần OCR


class FormResultStatus(str, enum.Enum):
    valid       = "valid"        # field trích xuất tin cậy, không cần soát
    need_review = "need_review"  # cần cán bộ soát lại (mặc định)
    invalid     = "invalid"      # field sai/không hợp lệ


class ResultConfirmStatus(str, enum.Enum):
    valid   = "valid"    # cán bộ xác nhận field hợp lệ
    invalid = "invalid"  # cán bộ xác nhận field không hợp lệ


class FormType(Base):
    __tablename__ = "form_types"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    type_name  = Column(String(100), unique=True, nullable=False, index=True)  # "ct01"
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    templates = relationship("FormTemplate", back_populates="form_type", lazy="noload")


class FormTemplate(Base):
    __tablename__ = "form_templates"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_type_id = Column(UUID(as_uuid=True), ForeignKey("form_types.id", ondelete="CASCADE"),
                          nullable=False, index=True)
    name         = Column(String(255), nullable=False)
    version      = Column(String(50), nullable=False, default="1.0")
    config_path  = Column(String(512), nullable=False)      # YAML config (local path hoặc S3 URL)
    template_url = Column(String(1024), nullable=True)      # URL file Word để user download & điền
    field_schema = Column(JSONB, nullable=True)             # mô tả field/section để validate + render
    is_active    = Column(Boolean, default=True, nullable=False)
    created_by   = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at   = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    form_type = relationship("FormType", back_populates="templates")


class Form(Base):
    __tablename__ = "forms"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    org_id       = Column(UUID(as_uuid=True), ForeignKey("organizations.id", ondelete="SET NULL"),
                          nullable=True, index=True)  # gửi về ai (phường tiếp nhận)
    submit_by    = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"),
                          nullable=True, index=True)  # ai là người submit form
    form_type_id = Column(UUID(as_uuid=True), ForeignKey("form_types.id", ondelete="SET NULL"),
                          nullable=True, index=True)  # loại đơn

    status     = Column(Enum(FormStatus), default=FormStatus.submitted, nullable=False, index=True)
    notification_on = Column(String(255), nullable=True)  # nơi nhận thông báo cuối cùng (email/sđt)
    review_note     = Column(Text, nullable=True)         # lý do/ghi chú khi duyệt/trả về
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    tamtru    = relationship("TamtruForm", back_populates="form", uselist=False,
                             cascade="all, delete-orphan", lazy="noload")
    evidences = relationship("Evidence", back_populates="form",
                             cascade="all, delete-orphan", lazy="noload",
                             order_by="Evidence.created_at")
    results   = relationship("FormResult", back_populates="form",
                             cascade="all, delete-orphan", lazy="noload",
                             order_by="FormResult.label")


class TamtruForm(Base):
    """Bảng con của Forms cho đơn đăng ký tạm trú (1:1 với forms). Mở rộng loại đơn khác tương tự."""
    __tablename__ = "tamtru_forms"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id            = Column(UUID(as_uuid=True), ForeignKey("forms.id", ondelete="CASCADE"),
                                nullable=False, unique=True)
    case               = Column(String(100), nullable=True)
    type               = Column(String(100), nullable=True)
    submit_type        = Column(String(100), nullable=True)  # hình thức nộp (themself/declare...)
    location_register  = Column(String(512), nullable=True)
    registered_user_cccd   = Column(String(12), nullable=True)   # CCCD người được khai báo thay đổi cư trú
    registered_user_name   = Column(String(255), nullable=True)
    registered_user_birth  = Column(Date, nullable=True)
    registered_user_gender = Column(String(20), nullable=True)
    registered_user_phone  = Column(String(20), nullable=True)
    registered_user_mail   = Column(String(255), nullable=True)
    register_content       = Column(Text, nullable=True)
    created_at         = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    form = relationship("Form", back_populates="tamtru")


class Evidence(Base):
    """File đính kèm của 1 form (ảnh đơn, tài liệu...). Một form có thể có nhiều evidence."""
    __tablename__ = "evidences"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id     = Column(UUID(as_uuid=True), ForeignKey("forms.id", ondelete="CASCADE"),
                         nullable=False, index=True)
    path_url    = Column(String(512), nullable=False)
    warped_img  = Column(String(512), nullable=True)   # S3 path của ảnh đã align/warp sau OCR
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    form = relationship("Form", back_populates="evidences")


class FormResult(Base):
    """Kết quả trích xuất của 1 form: mỗi field 1 dòng (cho phép cán bộ chỉnh/duyệt từng field)."""
    __tablename__ = "form_results"

    id              = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id         = Column(UUID(as_uuid=True), ForeignKey("forms.id", ondelete="CASCADE"),
                             nullable=False, index=True)
    position        = Column(JSONB, nullable=True)                  # vị trí field trên document: [x, y, w, h] pixel
    label           = Column(String(255), nullable=False)          # tên field (vd "ho_ten")
    raw_value       = Column(Text, nullable=True)                  # giá trị OCR thô
    suggested_value = Column(Text, nullable=True)                  # giá trị CSDL gợi ý (khi REVIEW/ERROR), null nếu PASS
    note            = Column(Text, nullable=True)                  # lý do verdict (vd: "đọc rõ nhưng khác CSDL")
    status          = Column(Enum(FormResultStatus), default=FormResultStatus.need_review,
                             nullable=False, index=True)           # valid | need_review | invalid
    created_at      = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    form     = relationship("Form", back_populates="results")
    confirms = relationship("ResultConfirm", back_populates="checkpoint",
                            cascade="all, delete-orphan", lazy="noload",
                            order_by="ResultConfirm.created_at")


class ResultConfirm(Base):
    """Lịch sử confirm của 1 form_result: mỗi lần cán bộ lưu draft tạo 1 dòng mới."""
    __tablename__ = "result_confirm"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    checkpoint_id = Column(UUID(as_uuid=True), ForeignKey("form_results.id", ondelete="CASCADE"),
                           nullable=False, index=True)
    confirmed_by = Column(UUID(as_uuid=True), nullable=True)
    created_at   = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    final_status = Column(Enum(ResultConfirmStatus), nullable=False)

    checkpoint = relationship("FormResult", back_populates="confirms")

