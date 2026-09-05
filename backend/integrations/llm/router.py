"""
LLMRouter Service — Milestone 11
Cascading LLM Router (OpenAI -> Gemini -> Deterministic Fallback) with database audit logging.
"""

import logging
import time
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session

from backend.integrations.llm.base import LLMProvider, LLMProviderError
from backend.integrations.llm.schemas import RecoveryDiagnosis
from backend.integrations.llm.openai_provider import OpenAIProvider
from backend.integrations.llm.gemini_provider import GeminiProvider
from backend.integrations.llm.deterministic_provider import DeterministicFallbackProvider
from backend.models.llm_invocation import LLMInvocation

logger = logging.getLogger(__name__)

# Class-level cooldown tracking for quota/rate limited providers
_provider_cooldowns: Dict[str, float] = {}

class LLMRouter:
    """Cascading router for LLM providers with automatic DB audit trail."""

    def __init__(self, providers: Optional[List[LLMProvider]] = None):
        if providers is not None:
            for p in providers:
                _provider_cooldowns.pop(p.name, None)
        self.providers: List[LLMProvider] = providers or [
            OpenAIProvider(),
            GeminiProvider(),
            DeterministicFallbackProvider(),
        ]

    def diagnose_case(
        self,
        context: Dict[str, Any],
        db: Optional[Session] = None,
        case_id: Optional[str] = None,
        batch_run_id: Optional[str] = None,
    ) -> RecoveryDiagnosis:
        """
        Diagnose payment failure context using cascading provider fallback.
        Audits every invocation attempt (success or failure) in the llm_invocations DB table.
        Guaranteed to return a valid RecoveryDiagnosis via DeterministicFallbackProvider.
        """
        fallback_triggered = False
        now = time.time()

        for idx, provider in enumerate(self.providers):
            # Check provider cooldown
            cooldown_until = _provider_cooldowns.get(provider.name, 0)
            if now < cooldown_until:
                fallback_triggered = True
                logger.info(f"[LLMRouter] Provider '{provider.name}' is in quota cooldown ({int(cooldown_until - now)}s remaining). Skipping.")
                continue

            try:
                logger.info(f"[LLMRouter] Attempting diagnosis with provider '{provider.name}' ({provider.model_name})...")
                diagnosis, metadata = provider.diagnose(context)

                # Log successful invocation
                if db:
                    inv = LLMInvocation(
                        recovery_case_id=case_id,
                        batch_run_id=batch_run_id,
                        provider=provider.name,
                        model=provider.model_name,
                        latency_ms=metadata.get("latency_ms", 0),
                        prompt_tokens=metadata.get("prompt_tokens", 0),
                        completion_tokens=metadata.get("completion_tokens", 0),
                        success=True,
                        error_message=None,
                        fallback_triggered=fallback_triggered,
                    )
                    db.add(inv)
                    db.flush()

                logger.info(f"[LLMRouter] Provider '{provider.name}' succeeded (latency: {metadata.get('latency_ms')}ms). Strategy: {diagnosis.recommended_strategy}")
                return diagnosis

            except LLMProviderError as err:
                fallback_triggered = True
                logger.warning(f"[LLMRouter] Provider '{provider.name}' failed: {err.message}")

                # If quota/rate limit error, trigger 60s cooldown
                err_str = str(err).lower()
                if "429" in err_str or "quota" in err_str or "exhausted" in err_str or "credit" in err_str:
                    _provider_cooldowns[provider.name] = time.time() + 60.0
                    logger.warning(f"[LLMRouter] Set 60s quota cooldown for provider '{provider.name}'.")

                if db:
                    inv = LLMInvocation(
                        recovery_case_id=case_id,
                        batch_run_id=batch_run_id,
                        provider=provider.name,
                        model=provider.model_name,
                        latency_ms=0,
                        prompt_tokens=0,
                        completion_tokens=0,
                        success=False,
                        error_message=str(err),
                        fallback_triggered=True,
                    )
                    db.add(inv)
                    db.flush()

            except Exception as unhandled_err:
                fallback_triggered = True
                logger.error(f"[LLMRouter] Unexpected error in provider '{provider.name}': {unhandled_err}")

                err_str = str(unhandled_err).lower()
                if "429" in err_str or "quota" in err_str or "exhausted" in err_str or "credit" in err_str:
                    _provider_cooldowns[provider.name] = time.time() + 60.0

                if db:
                    inv = LLMInvocation(
                        recovery_case_id=case_id,
                        batch_run_id=batch_run_id,
                        provider=provider.name,
                        model=provider.model_name,
                        latency_ms=0,
                        prompt_tokens=0,
                        completion_tokens=0,
                        success=False,
                        error_message=str(unhandled_err),
                        fallback_triggered=True,
                    )
                    db.add(inv)
                    db.flush()

        # Fallback to absolute emergency deterministic provider if all configured providers fail
        logger.error("[LLMRouter] All configured providers failed! Executing emergency DeterministicFallbackProvider.")
        emergency = DeterministicFallbackProvider()
        diag, meta = emergency.diagnose(context)
        if db:
            inv = LLMInvocation(
                recovery_case_id=case_id,
                batch_run_id=batch_run_id,
                provider=emergency.name,
                model=emergency.model_name,
                latency_ms=meta.get("latency_ms", 0),
                prompt_tokens=0,
                completion_tokens=0,
                success=True,
                error_message="All prior providers failed; emergency fallback executed",
                fallback_triggered=True,
            )
            db.add(inv)
            db.flush()

        return diag
