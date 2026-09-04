"""
Transaction Database Model
"""

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from sqlalchemy import String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database.session import Base
from backend.models.enums import TransactionStatus, FailureCategory, DataCategory

if TYPE_CHECKING:
    from backend.models.customer import Customer
    from backend.models.recovery_case import RecoveryCase

class Transaction(Base):
    """Payment transaction entity mirroring Razorpay objects with error metadata."""
    __tablename__ = "transactions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    razorpay_payment_id: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    razorpay_order_id: Mapped[str | None] = mapped_column(
        String(255), nullable=True, index=True
    )
    customer_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("customers.id", ondelete="SET NULL"), nullable=True, index=True
    )
    
    # Amount stored safely as integer paise (e.g. 50000 = ₹500.00)
    amount_paise: Mapped[int] = mapped_column(Integer, nullable=False)
    currency: Mapped[str] = mapped_column(String(10), default="INR")
    status: Mapped[str] = mapped_column(
        String(50), default=TransactionStatus.FAILED.value, index=True
    )
    
    # Diagnostic error metadata
    failure_category: Mapped[str | None] = mapped_column(
        String(50), nullable=True, index=True
    )
    error_code: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_description: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_source: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_step: Mapped[str | None] = mapped_column(String(100), nullable=True)
    error_reason: Mapped[str | None] = mapped_column(String(100), nullable=True)
    payment_method: Mapped[str | None] = mapped_column(String(50), nullable=True)
    
    # Explicit data category: OBSERVED, VERIFIED, SIMULATED, PROJECTED
    data_source: Mapped[str] = mapped_column(
        String(50), default=DataCategory.SIMULATED.value, index=True
    )
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc), index=True
    )

    # Relationships
    customer: Mapped["Customer | None"] = relationship("Customer", back_populates="transactions")
    recovery_case: Mapped["RecoveryCase | None"] = relationship(
        "RecoveryCase", back_populates="transaction", uselist=False, cascade="all, delete-orphan"
    )
