"""
Segment Database Model
"""

import uuid
from datetime import datetime, timezone
from typing import List, TYPE_CHECKING
from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database.session import Base

if TYPE_CHECKING:
    from backend.models.recovery_case import RecoveryCase
    from backend.models.recovery_strategy import RecoveryStrategy

class Segment(Base):
    """Segment entity defining payment populations for strategy performance tracking."""
    __tablename__ = "segments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    failure_category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    amount_range: Mapped[str] = mapped_column(String(50), nullable=False)
    customer_type: Mapped[str | None] = mapped_column(String(50), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    recovery_cases: Mapped[List["RecoveryCase"]] = relationship("RecoveryCase", back_populates="segment")
    recovery_strategies: Mapped[List["RecoveryStrategy"]] = relationship(
        "RecoveryStrategy", back_populates="segment", cascade="all, delete-orphan"
    )
