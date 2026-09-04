"""
Google Gemini Provider Implementation — Milestone 11
Integrates Google Gemini models (gemini-1.5-pro / gemini-2.0-flash) with structured JSON output parsing.
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

class GeminiProvider(LLMProvider):
    """Google Gemini LLM Provider."""

    def __init__(self, api_key: str | None = None, model: str = "gemini-1.5-pro"):
        self._api_key = api_key or os.getenv("GEMINI_API_KEY", getattr(settings, "GEMINI_API_KEY", ""))
        self._model = model

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def model_name(self) -> str:
        return self._model

    def diagnose(self, context: Dict[str, Any]) -> Tuple[RecoveryDiagnosis, Dict[str, Any]]:
        # Check simulation override flag
        if getattr(settings, "SIMULATE_GEMINI_FAILURE", False):
            logger.warning("[GeminiProvider] Failure simulated via SIMULATE_GEMINI_FAILURE setting.")
            raise LLMProviderError(self.name, "Simulated Gemini provider failure.")

        if not self._api_key:
            logger.info("[GeminiProvider] No GEMINI_API_KEY configured.")
            raise LLMProviderError(self.name, "Missing GEMINI_API_KEY.")

        start_t = time.perf_counter()
        user_prompt = build_user_prompt(context)
        combined_prompt = f"{SYSTEM_DIAGNOSIS_PROMPT}\n\n{user_prompt}"

        try:
            # Try new google.genai SDK first
            try:
                from google import genai
                from google.genai import types

                client = genai.Client(api_key=self._api_key)
                response = client.models.generate_content(
                    model=self._model,
                    contents=combined_prompt,
                    config=types.GenerateContentConfig(
                        response_mime_type="application/json",
                        temperature=0.2,
                    ),
                )
                raw_text = response.text or "{}"
            except (ImportError, Exception) as sub_e:
                # Fall back to google.generativeai if available
                import google.generativeai as genai_legacy
                genai_legacy.configure(api_key=self._api_key)
                model_inst = genai_legacy.GenerativeModel(
                    model_name=self._model,
                    generation_config={"response_mime_type": "application/json", "temperature": 0.2}
                )
                response = model_inst.generate_content(combined_prompt)
                raw_text = response.text or "{}"

            # Strip markdown code blocks if present
            clean_text = raw_text.strip()
            if clean_text.startswith("```json"):
                clean_text = clean_text[7:]
            if clean_text.startswith("```"):
                clean_text = clean_text[3:]
            if clean_text.endswith("```"):
                clean_text = clean_text[:-3]

            parsed_json = json.loads(clean_text.strip())
            diagnosis = RecoveryDiagnosis.model_validate(parsed_json)

            elapsed_ms = int((time.perf_counter() - start_t) * 1000)
            metadata = {
                "latency_ms": max(1, elapsed_ms),
                "prompt_tokens": 0,
                "completion_tokens": 0,
            }

            return diagnosis, metadata

        except LLMProviderError:
            raise
        except Exception as e:
            logger.error(f"[GeminiProvider] API Error: {e}")
            raise LLMProviderError(self.name, f"Gemini API call failed: {str(e)}", original_exception=e)
