"""
Pydantic Schemas for LLM Diagnosis and Recommendation Outputs — Milestone 11
"""

from pydantic import BaseModel, Field, field_validator
from backend.models.enums import FailureCategory, StrategyType

class RecoveryDiagnosis(BaseModel):
    """Structured Pydantic output schema returned by all LLM providers."""
    failure_category: str = Field(
        ...,
        description="Categorized root cause of payment failure (e.g. AUTHENTICATION_FAILURE, INSUFFICIENT_FUNDS)",
    )
    diagnosis: str = Field(
        ...,
        description="Detailed narrative explanation of the failure diagnosis",
    )
    recoverability_score: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Propensity score indicating likelihood of successful recovery (0.0 to 1.0)",
    )
    confidence: float = Field(
        ...,
        ge=0.0,
        le=1.0,
        description="Confidence score of the AI diagnosis/recommendation (0.0 to 1.0)",
    )
    recommended_strategy: str = Field(
        ...,
        description="Recommended recovery strategy (e.g. PAYMENT_LINK, RETRY, REMINDER, ESCALATED)",
    )
    reasoning_summary: str = Field(
        ...,
        description="Concise rationale for selecting the recommended strategy",
    )

    @field_validator("failure_category")
    @classmethod
    def validate_failure_category(cls, v: str) -> str:
        valid_cats = {e.value for e in FailureCategory}
        if v not in valid_cats:
            # Normalize or fallback if close match, else raiseValueError
            upper_v = v.upper()
            if upper_v in valid_cats:
                return upper_v
            raise ValueError(f"Invalid failure_category '{v}'. Must be one of {valid_cats}")
        return v

    @field_validator("recommended_strategy")
    @classmethod
    def validate_recommended_strategy(cls, v: str) -> str:
        valid_strats = {e.value for e in StrategyType}
        if v not in valid_strats:
            upper_v = v.upper()
            if upper_v in valid_strats:
                return upper_v
            raise ValueError(f"Invalid recommended_strategy '{v}'. Must be one of {valid_strats}")
        return v
