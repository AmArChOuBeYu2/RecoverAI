"""
Policy Configuration Schema & Defaults for RecoverAI.
Defines typed, configurable policy thresholds in integer paise.
"""

from pydantic import BaseModel, Field, ConfigDict
from backend.config import settings

class PolicyConfig(BaseModel):
    """Typed configuration object for RecoverAI safety policy thresholds."""
    model_config = ConfigDict(populate_by_name=True)

    policy_version: str = Field(default="v1.0", description="Policy version identifier")
    
    # Financial thresholds stored in integer paise
    high_value_threshold_paise: int = Field(
        default=1000000, description="High-value threshold: ₹10,000.00 (1,000,000 paise)"
    )
    max_automated_action_amount_paise: int = Field(
        default=5000000, description="Maximum automated action cap: ₹50,000.00 (5,000,000 paise)"
    )

    # Frequency & Cooldown Limits
    max_retries: int = Field(default=2, description="Maximum recovery attempts per transaction")
    max_contacts_24h: int = Field(default=3, description="Maximum customer contacts per 24 hours")
    cooldown_minutes: int = Field(default=60, description="Minimum cooldown minutes between attempts")

    # Communication Hours (IST)
    contact_start_hour: int = Field(default=9, description="Communication start hour IST (9 AM)")
    contact_end_hour: int = Field(default=21, description="Communication end hour IST (9 PM / 21:00)")

    # AI & Recovery Confidence Thresholds
    min_ai_confidence: float = Field(default=0.60, description="Minimum AI confidence for automated action")
    min_recoverability_score: float = Field(default=0.30, description="Minimum recoverability propensity score")

    @classmethod
    def from_settings(cls) -> "PolicyConfig":
        """Load policy configuration from global application settings."""
        return cls(
            high_value_threshold_paise=getattr(settings, "HIGH_VALUE_THRESHOLD_PAISE", 1000000),
            max_automated_action_amount_paise=getattr(settings, "MAX_AUTOMATED_ACTION_AMOUNT_PAISE", 5000000),
            max_retries=getattr(settings, "MAX_RETRIES", 2),
            max_contacts_24h=getattr(settings, "MAX_CONTACTS_24H", 3),
            cooldown_minutes=getattr(settings, "COOLDOWN_MINUTES", 60),
            contact_start_hour=getattr(settings, "CONTACT_START_HOUR", 9),
            contact_end_hour=getattr(settings, "CONTACT_END_HOUR", 21),
            min_ai_confidence=getattr(settings, "MIN_AI_CONFIDENCE", 0.60),
            min_recoverability_score=getattr(settings, "MIN_RECOVERABILITY", 0.30),
        )
