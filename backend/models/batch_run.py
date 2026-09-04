"""
BatchRun Database Model
"""

import uuid
from datetime import datetime, timezone
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Integer, DateTime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database.session import Base

if TYPE_CHECKING:
    from backend.models.policy_simulation import PolicySimulation
    from backend.models.llm_invocation import LLMInvocation

class BatchRun(Base):
    """Batch Run entity tracking execution of batch evaluation runs."""
    __tablename__ = "batch_runs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    run_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    total_processed: Mapped[int] = mapped_column(Integer, default=0)
    total_recovered_paise: Mapped[int] = mapped_column(Integer, default=0)
    success_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[str] = mapped_column(String(50), default="COMPLETED", index=True)
    
    started_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Relationships
    policy_simulations: Mapped[List["PolicySimulation"]] = relationship(
        "PolicySimulation", back_populates="batch_run"
    )
    llm_invocations: Mapped[List["LLMInvocation"]] = relationship(
        "LLMInvocation", back_populates="batch_run"
    )
