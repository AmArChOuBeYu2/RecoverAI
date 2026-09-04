"""
PolicyDecision Database Model
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database.session import Base
from backend.models.enums import PolicyDecisionType

if TYPE_CHECKING:
    from backend.models.recovery_case import RecoveryCase

class PolicyDecision(Base):
    """Policy Decision entity recording safety policy gate results."""
    __tablename__ = "policy_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recovery_case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recovery_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    decision: Mapped[str] = mapped_column(
        String(50), default=PolicyDecisionType.APPROVE.value, index=True
    )
    evaluated_rules: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    blocking_rule: Mapped[str | None] = mapped_column(String(100), nullable=True)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    evaluated_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    recovery_case: Mapped["RecoveryCase"] = relationship(
        "RecoveryCase", back_populates="policy_decisions"
    )
