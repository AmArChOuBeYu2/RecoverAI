"""
RecoveryCase Database Model
"""

import uuid
from datetime import datetime, timezone
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Integer, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database.session import Base
from backend.models.enums import RecoveryCaseStatus

if TYPE_CHECKING:
    from backend.models.transaction import Transaction
    from backend.models.customer import Customer
    from backend.models.segment import Segment
    from backend.models.recovery_decision import RecoveryDecision
    from backend.models.recovery_action import RecoveryAction
    from backend.models.policy_decision import PolicyDecision
    from backend.models.strategy_outcome import StrategyOutcome
    from backend.models.audit_event import AuditEvent
    from backend.models.llm_invocation import LLMInvocation

class RecoveryCase(Base):
    """Recovery Case state machine tracking recovery execution per failed transaction."""
    __tablename__ = "recovery_cases"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    transaction_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("transactions.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    segment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("segments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    
    status: Mapped[str] = mapped_column(
        String(50), default=RecoveryCaseStatus.DETECTED.value, index=True
    )
    recoverability_score: Mapped[float | None] = mapped_column(Float, nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    
    is_eligible: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    ineligibility_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_terminal: Mapped[bool] = mapped_column(Boolean, default=False, index=True)
    
    detected_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="recovery_case")
    customer: Mapped["Customer | None"] = relationship("Customer", back_populates="recovery_cases")
    segment: Mapped["Segment | None"] = relationship("Segment", back_populates="recovery_cases")
    
    decisions: Mapped[List["RecoveryDecision"]] = relationship(
        "RecoveryDecision", back_populates="recovery_case", cascade="all, delete-orphan"
    )
    actions: Mapped[List["RecoveryAction"]] = relationship(
        "RecoveryAction", back_populates="recovery_case", cascade="all, delete-orphan"
    )
    policy_decisions: Mapped[List["PolicyDecision"]] = relationship(
        "PolicyDecision", back_populates="recovery_case", cascade="all, delete-orphan"
    )
    outcomes: Mapped[List["StrategyOutcome"]] = relationship(
        "StrategyOutcome", back_populates="recovery_case", cascade="all, delete-orphan"
    )
    audit_events: Mapped[List["AuditEvent"]] = relationship(
        "AuditEvent", back_populates="recovery_case"
    )
    llm_invocations: Mapped[List["LLMInvocation"]] = relationship(
        "LLMInvocation", back_populates="recovery_case"
    )
