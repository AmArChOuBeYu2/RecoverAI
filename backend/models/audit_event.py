"""
AuditEvent Database Model
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database.session import Base

if TYPE_CHECKING:
    from backend.models.recovery_case import RecoveryCase

class AuditEvent(Base):
    """Audit Event entity recording immutable state transitions, policy checks, and webhooks."""
    __tablename__ = "audit_events"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recovery_case_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("recovery_cases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Unique event_id provides webhook idempotency prevention
    event_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    
    actor: Mapped[str] = mapped_column(String(100), default="SYSTEM")
    description: Mapped[str] = mapped_column(Text, nullable=False)
    details: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )

    # Relationships
    recovery_case: Mapped["RecoveryCase | None"] = relationship(
        "RecoveryCase", back_populates="audit_events"
    )
