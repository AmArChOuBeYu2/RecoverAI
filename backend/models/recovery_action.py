"""
RecoveryAction Database Model
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, Text, ForeignKey, JSON, Index
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database.session import Base
from backend.models.enums import ActionExecutionMode

if TYPE_CHECKING:
    from backend.models.recovery_case import RecoveryCase

class RecoveryAction(Base):
    """Recovery Action entity recording intervention execution and payment link links."""
    __tablename__ = "recovery_actions"
    __table_args__ = (
        Index("idx_case_action_status", "recovery_case_id", "action_type", "status"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recovery_case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recovery_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    action_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    execution_mode: Mapped[str] = mapped_column(
        String(50), default=ActionExecutionMode.SIMULATED.value, index=True
    )
    
    razorpay_payment_link_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, unique=True, index=True
    )

    payment_link_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), default="PENDING", index=True)
    
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    executed_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    recovery_case: Mapped["RecoveryCase"] = relationship("RecoveryCase", back_populates="actions")
