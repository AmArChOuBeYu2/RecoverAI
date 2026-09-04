"""
Customer Database Model
"""

import uuid
from datetime import datetime, timezone
from typing import List, TYPE_CHECKING
from sqlalchemy import String, Integer, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship
from backend.database.session import Base
from backend.models.enums import CustomerType

if TYPE_CHECKING:
    from backend.models.transaction import Transaction
    from backend.models.recovery_case import RecoveryCase

class Customer(Base):
    """Customer entity tracking payment history, type, and communication frequency."""
    __tablename__ = "customers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    email: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    customer_type: Mapped[str] = mapped_column(String(50), default=CustomerType.NEW.value, index=True)
    
    total_transactions: Mapped[int] = mapped_column(Integer, default=0)
    failed_transactions: Mapped[int] = mapped_column(Integer, default=0)
    successful_transactions: Mapped[int] = mapped_column(Integer, default=0)
    
    last_failed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    contacts_count_24h: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # Relationships
    transactions: Mapped[List["Transaction"]] = relationship(
        "Transaction", back_populates="customer", cascade="all, delete-orphan"
    )
    recovery_cases: Mapped[List["RecoveryCase"]] = relationship(
        "RecoveryCase", back_populates="customer"
    )
