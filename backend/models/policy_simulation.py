"""
PolicySimulation Database Model
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, Integer, Float, DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database.session import Base
from backend.models.enums import DataCategory

if TYPE_CHECKING:
    from backend.models.batch_run import BatchRun

class PolicySimulation(Base):
    """Policy Simulation entity recording read-only simulator results."""
    __tablename__ = "policy_simulations"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    batch_run_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("batch_runs.id", ondelete="SET NULL"), nullable=True, index=True
    )
    
    policy_name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    total_transactions: Mapped[int] = mapped_column(Integer, default=0)
    revenue_at_risk_paise: Mapped[int] = mapped_column(Integer, default=0)
    eligible_count: Mapped[int] = mapped_column(Integer, default=0)
    eligible_revenue_paise: Mapped[int] = mapped_column(Integer, default=0)
    projected_recovered_paise: Mapped[int] = mapped_column(Integer, default=0)
    projected_recovery_rate: Mapped[float] = mapped_column(Float, default=0.0)
    
    actions_projected: Mapped[int] = mapped_column(Integer, default=0)
    policy_blocks_projected: Mapped[int] = mapped_column(Integer, default=0)
    escalations_projected: Mapped[int] = mapped_column(Integer, default=0)
    contacts_projected: Mapped[int] = mapped_column(Integer, default=0)
    
    simulation_mode: Mapped[str] = mapped_column(
        String(50), default=DataCategory.PROJECTED.value, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    batch_run: Mapped["BatchRun | None"] = relationship("BatchRun", back_populates="policy_simulations")
