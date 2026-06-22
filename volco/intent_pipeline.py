"""Main entry points for the Vella intent processing pipeline."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException

from volco.intent.classifier import IntentClassifier
from volco.intent.router import IntentRouter
from volco.models.intent_models import IntentRequest, IntentResponse

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/intent", tags=["intent"])


async def process_text(text: str) -> dict[str, Any]:
    """Classify text, route the intent, execute the action, and return a result."""

    clean_text = text.strip()
    if not clean_text:
        return {
            "status": "error",
            "message": "No text was provided.",
            "intent": "conversation",
            "action": "call_llm",
            "error": "empty_text",
        }

    classifier = IntentClassifier()
    intent_data = await classifier.classify(clean_text)

    intent_router = IntentRouter()
    result = await intent_router.route(intent_data)
    logger.info("Processed intent=%s action=%s", result.get("intent"), result.get("action"))
    return result


@router.post("/process", response_model=IntentResponse)
async def process_intent_endpoint(request: IntentRequest) -> dict[str, Any]:
    """Process text through Vella's intent routing pipeline."""

    result = await process_text(request.text)
    if result.get("status") == "error" and result.get("error") == "empty_text":
        raise HTTPException(status_code=400, detail=result["message"])
    return result
