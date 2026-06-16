import uuid
from app.database import Base
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import (Column, String, DateTime, ForeignKey)

class Evidence(Base):
    __tablename__ = "evidences"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    form_id    = Column(UUID(as_uuid=True), ForeignKey("forms.id", ondelete="CASCADE"),
                        nullable=False, index=True)
    path_url   = Column(String(512), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    form = relationship("Form", back_populates="evidences")
