"""Chat action for Vella conversation fallbacks."""

from __future__ import annotations

import logging
import os
from typing import Any

from volco.services.ollama_client import OllamaClient, OllamaClientError

logger = logging.getLogger(__name__)

CHAT_MODEL = "qwen2.5:3b"

async def handle(text: str, client: OllamaClient | None = None, model: str | None = None) -> dict[str, Any]:
    """Call the main chat LLM for normal conversation."""

    ollama = client or OllamaClient(timeout_seconds=60.0)
    model_name = model or CHAT_MODEL
    prompt = f"""You are Vella, a concise and helpful voice assistant.
Answer the user's message naturally.

User: {text}
Vella:"""

    try:
        message = await ollama.generate(model_name, prompt)
    except OllamaClientError as exc:
        logger.exception("Chat action failed.")
        return {
            "status": "error",
            "message": "I could not reach the chat model right now.",
            "error": str(exc),
        }

    return {
        "status": "success",
        "message": message,
    }
