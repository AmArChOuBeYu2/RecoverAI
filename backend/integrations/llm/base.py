"""
Abstract Base Class & Exceptions for LLM Providers — Milestone 11
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Tuple
from backend.integrations.llm.schemas import RecoveryDiagnosis

class LLMProviderError(Exception):
    """Raised when an LLM provider fails to generate or parse a diagnosis."""
    def __init__(self, provider_name: str, message: str, original_exception: Exception | None = None):
        super().__init__(f"[{provider_name}] {message}")
        self.provider_name = provider_name
        self.message = message
        self.original_exception = original_exception

class LLMProvider(ABC):
    """Abstract interface for LLM diagnosis and strategy providers."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Name of the provider (e.g. 'openai', 'gemini', 'deterministic')."""
        pass

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Model Identifier (e.g. 'gpt-4o', 'gemini-1.5-pro', 'rule-engine-v1')."""
        pass

    @abstractmethod
    def diagnose(self, context: Dict[str, Any]) -> Tuple[RecoveryDiagnosis, Dict[str, Any]]:
        """
        Evaluate case context and return a structured RecoveryDiagnosis along with metadata:
        Returns: (diagnosis_object, metadata_dict)
        where metadata_dict includes:
          - latency_ms: int
          - prompt_tokens: int
          - completion_tokens: int
        Raises LLMProviderError if diagnosis fails.
        """
        pass
