"""Parsing helpers for model-produced intent JSON."""

from __future__ import annotations

import json
import logging
import re
from typing import Any

from pydantic import ValidationError

from volco.models.intent_models import IntentModel, validate_intent_payload

logger = logging.getLogger(__name__)


def fallback_intent(text: str) -> dict[str, str]:
    """Return the safe conversation fallback for malformed classifier output."""

    return {
        "intent": "conversation",
        "action": "call_llm",
        "text": text,
    }


def _extract_json_object(raw_response: str) -> str:
    """Extract the first JSON object from a raw LLM response."""

    cleaned = raw_response.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise ValueError("No JSON object found in intent response.")

    return cleaned[start : end + 1]


def parse_intent_response(raw_response: str, original_text: str) -> dict[str, Any]:
    """Parse and validate an intent classifier response.

    Invalid JSON, unsupported intents, and missing required values all fall back
    to the conversation intent so the assistant can still answer the user.
    """

    try:
        json_text = _extract_json_object(raw_response)
        payload = json.loads(json_text)
        if not isinstance(payload, dict):
            raise ValueError("Intent response JSON must be an object.")

        intent: IntentModel = validate_intent_payload(payload)
        if hasattr(intent, "model_dump"):
            return intent.model_dump()
        return intent.dict()
    except (json.JSONDecodeError, ValidationError, ValueError, TypeError) as exc:
        logger.warning("Falling back to conversation intent: %s", exc)
        return fallback_intent(original_text)
