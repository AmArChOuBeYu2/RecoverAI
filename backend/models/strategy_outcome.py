"""
StrategyOutcome Database Model
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, Integer, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database.session import Base
from backend.models.enums import OutcomeSource

if TYPE_CHECKING:
    from backend.models.recovery_case import RecoveryCase
    from backend.models.recovery_strategy import RecoveryStrategy
    from backend.models.segment import Segment

class StrategyOutcome(Base):
    """Strategy Outcome attribution entity closing the learning loop."""
    __tablename__ = "strategy_outcomes"
    __table_args__ = (
        UniqueConstraint("recovery_case_id", name="uq_strategy_outcome_case"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recovery_case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recovery_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    recovery_strategy_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("recovery_strategies.id", ondelete="SET NULL"), nullable=True, index=True
    )
    segment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("segments.id", ondelete="SET NULL"), nullable=True, index=True
    )
    
    strategy_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    outcome: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # RECOVERED, NOT_RECOVERED, PENDING, EXPIRED
    amount_recovered_paise: Mapped[int] = mapped_column(Integer, default=0)
    
    # Explicit evidence source: VERIFIED, SIMULATED, PROJECTED
    outcome_source: Mapped[str] = mapped_column(
        String(50), default=OutcomeSource.SIMULATED.value, index=True
    )
    
    attributed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    recovery_case: Mapped["RecoveryCase"] = relationship("RecoveryCase", back_populates="outcomes")
    recovery_strategy: Mapped["RecoveryStrategy | None"] = relationship(
        "RecoveryStrategy", back_populates="outcomes"
    )
    segment: Mapped["Segment | None"] = relationship("Segment")
