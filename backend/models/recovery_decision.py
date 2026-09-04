"""
RecoveryDecision Database Model
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, Float, DateTime, Text, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database.session import Base

if TYPE_CHECKING:
    from backend.models.recovery_case import RecoveryCase

class RecoveryDecision(Base):
    """Recovery Decision entity recording AI diagnosis, strategy selection, and evidence."""
    __tablename__ = "recovery_decisions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recovery_case_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("recovery_cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    
    ai_diagnosis: Mapped[str | None] = mapped_column(Text, nullable=True)
    ai_recommended_strategy: Mapped[str | None] = mapped_column(String(50), nullable=True)
    ai_confidence: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    selected_strategy: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    reasoning_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Unstructured evidence payloads stored in JSON
    strategy_evidence: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    competing_strategies: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    
    llm_provider: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    recovery_case: Mapped["RecoveryCase"] = relationship("RecoveryCase", back_populates="decisions")
