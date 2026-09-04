"""
LLMInvocation Database Model
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database.session import Base

if TYPE_CHECKING:
    from backend.models.recovery_case import RecoveryCase
    from backend.models.batch_run import BatchRun

class LLMInvocation(Base):
    """LLM Invocation entity logging provider attempts, latency, token usage, and fallbacks."""
    __tablename__ = "llm_invocations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    recovery_case_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("recovery_cases.id", ondelete="SET NULL"), nullable=True, index=True
    )
    batch_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("batch_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    
    provider: Mapped[str] = mapped_column(String(50), nullable=False, index=True) # openai, gemini, deterministic
    model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    latency_ms: Mapped[int] = mapped_column(Integer, default=0)
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0)
    
    success: Mapped[bool] = mapped_column(Boolean, default=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    fallback_triggered: Mapped[bool] = mapped_column(Boolean, default=False)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    recovery_case: Mapped["RecoveryCase | None"] = relationship(
        "RecoveryCase", back_populates="llm_invocations"
    )
    batch_run: Mapped["BatchRun | None"] = relationship(
        "BatchRun", back_populates="llm_invocations"
    )
