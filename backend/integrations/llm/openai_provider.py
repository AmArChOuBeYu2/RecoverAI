"""
OpenAI Provider Implementation — Milestone 11
Integrates OpenAI GPT models (GPT-4o) with structured JSON schema outputs and exception handling.
"""

import os
import json
import time
import logging
from typing import Dict, Any, Tuple

from backend.config import settings
from backend.integrations.llm.base import LLMProvider, LLMProviderError
from backend.integrations.llm.schemas import RecoveryDiagnosis
from backend.integrations.llm.prompts import SYSTEM_DIAGNOSIS_PROMPT, build_user_prompt

logger = logging.getLogger(__name__)

class OpenAIProvider(LLMProvider):
    """OpenAI GPT-4o LLM Provider."""

    def __init__(self, api_key: str | None = None, model: str = "gpt-4o"):
        self._api_key = api_key or os.getenv("OPENAI_API_KEY", getattr(settings, "OPENAI_API_KEY", ""))
        self._model = model

    @property
    def name(self) -> str:
        return "openai"

    @property
    def model_name(self) -> str:
        return self._model

    def diagnose(self, context: Dict[str, Any]) -> Tuple[RecoveryDiagnosis, Dict[str, Any]]:
        # Check simulation override flag
        if getattr(settings, "SIMULATE_OPENAI_FAILURE", False):
            logger.warning("[OpenAIProvider] Failure simulated via SIMULATE_OPENAI_FAILURE setting.")
            raise LLMProviderError(self.name, "Simulated OpenAI provider failure.")

        if not self._api_key:
            logger.info("[OpenAIProvider] No OPENAI_API_KEY configured.")
            raise LLMProviderError(self.name, "Missing OPENAI_API_KEY.")

        start_t = time.perf_counter()
        user_prompt = build_user_prompt(context)

        try:
            from openai import OpenAI
            client = OpenAI(api_key=self._api_key)

            response = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": SYSTEM_DIAGNOSIS_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
                timeout=10.0,
            )

            raw_content = response.choices[0].message.content or "{}"
            parsed_json = json.loads(raw_content)

            diagnosis = RecoveryDiagnosis.model_validate(parsed_json)

            elapsed_ms = int((time.perf_counter() - start_t) * 1000)
            usage = getattr(response, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", 0) if usage else 0
            completion_tokens = getattr(usage, "completion_tokens", 0) if usage else 0

            metadata = {
                "latency_ms": max(1, elapsed_ms),
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }

            return diagnosis, metadata

        except LLMProviderError:
            raise
        except Exception as e:
            logger.error(f"[OpenAIProvider] API Error: {e}")
            raise LLMProviderError(self.name, f"OpenAI API call failed: {str(e)}", original_exception=e)
