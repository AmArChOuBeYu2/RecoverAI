"""
RecoveryStrategy Database Model
"""

import uuid
from datetime import datetime, timezone
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database.session import Base
from backend.models.enums import DataCategory, ConfidenceLevel

if TYPE_CHECKING:
    from backend.models.segment import Segment
    from backend.models.strategy_outcome import StrategyOutcome

class RecoveryStrategy(Base):
    """Recovery Strategy performance tracking entity per segment."""
    __tablename__ = "recovery_strategies"
    __table_args__ = (
        UniqueConstraint("segment_id", "strategy_type", name="uq_segment_strategy"),
    )

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    segment_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("segments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    strategy_type: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    
    attempt_count: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    total_recovered_paise: Mapped[int] = mapped_column(Integer, default=0)
    
    recovery_rate: Mapped[float] = mapped_column(Float, default=0.0)
    wilson_lower_bound: Mapped[float] = mapped_column(Float, default=0.0)
    avg_recovery_amount_paise: Mapped[float] = mapped_column(Float, default=0.0)
    
    sample_size_sufficient: Mapped[bool] = mapped_column(Boolean, default=False)
    data_source: Mapped[str] = mapped_column(
        String(50), default=DataCategory.OBSERVED.value, index=True
    )
    confidence_level: Mapped[str] = mapped_column(
        String(50), default=ConfidenceLevel.INSUFFICIENT.value
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    segment: Mapped["Segment"] = relationship("Segment", back_populates="recovery_strategies")
    outcomes: Mapped[List["StrategyOutcome"]] = relationship(
        "StrategyOutcome", back_populates="recovery_strategy"
    )
