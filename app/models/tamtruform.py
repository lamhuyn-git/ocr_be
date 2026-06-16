
import uuid
from app.database import Base
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy import (Column, String, DateTime, ForeignKey)

class TamtruForm(Base):
    __tablename__ = "tamtru_forms"

    id                 = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id            = Column(UUID(as_uuid=True), ForeignKey("forms.id", ondelete="CASCADE"),
                                nullable=False, unique=True)
    case               = Column(String(100), nullable=True)
    type               = Column(String(100), nullable=True)
    location_register  = Column(String(512), nullable=True)
    registered_user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    register_content   = Column(JSONB, nullable=True)
    created_at         = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    form = relationship("Form", back_populates="tamtru")
