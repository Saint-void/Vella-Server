"""Intent classifier powered by a small Ollama model."""

from __future__ import annotations

import logging
import os
from typing import Any

from volco.intent.parser import fallback_intent, parse_intent_response
from volco.intent.rules import detect_intent
from volco.services.ollama_client import OllamaClient, OllamaClientError

logger = logging.getLogger(__name__)


INTENT_MODEL = "qwen2.5:1.5b"


class IntentClassifier:
    """Classify user text into a supported assistant intent."""

    def __init__(self, client: OllamaClient | None = None, model: str | None = None) -> None:
        self.client = client or OllamaClient(timeout_seconds=15.0)
        self.model = model or INTENT_MODEL

    async def classify(self, text: str) -> dict[str, Any]:
        """Classify text and return a validated intent dictionary."""

        clean_text = text.strip()
        if not clean_text:
            return fallback_intent(text)

        rule_intent = detect_intent(clean_text)
        if rule_intent is not None:
            logger.info("Matched deterministic intent: %s", rule_intent.get("intent"))
            return rule_intent

        prompt = self._build_prompt(clean_text)
        try:
            raw_response = await self.client.generate(self.model, prompt)
        except OllamaClientError as exc:
            logger.warning("Intent classifier failed, falling back to conversation: %s", exc)
            return fallback_intent(clean_text)

        return parse_intent_response(raw_response, clean_text)

    def _build_prompt(self, text: str) -> str:
        return f"""You are Vella's intent classifier.

    Return ONLY valid JSON.
    Do not use markdown.
    Do not explain your answer.
    Do not include extra text before or after the JSON.

    Supported intents:
    1. spotify_play
    2. spotify_play_playlist
    3. spotify_play_album
    4. spotify_next
    5. spotify_previous
    6. spotify_resume
    7. spotify_pause
    8. conversation

    Schemas:
    - spotify_play: {{"intent":"spotify_play","action":"spotify_play","song":"<song>","artist":"<artist or null>"}}
    - spotify_play_playlist: {{"intent":"spotify_play_playlist","action":"spotify_play_playlist","playlist":"<playlist name>"}}
    - spotify_play_album: {{"intent":"spotify_play_album","action":"spotify_play_album","album":"<album name>"}}
    - spotify_next: {{"intent":"spotify_next","action":"spotify_next"}}
    - spotify_previous: {{"intent":"spotify_previous","action":"spotify_previous"}}
    - spotify_resume: {{"intent":"spotify_resume","action":"spotify_resume"}}
    - spotify_pause: {{"intent":"spotify_pause","action":"spotify_pause"}}
    - conversation: {{"intent":"conversation","action":"call_llm","text":"<original user text>"}}

    Examples:
    User: Play Hope by NF
    JSON: {{"intent":"spotify_play","action":"spotify_play","song":"Hope","artist":"NF"}}

    User: Play my NF playlist
    JSON: {{"intent":"spotify_play_playlist","action":"spotify_play_playlist","playlist":"NF"}}

    User: Play the Fear album
    JSON: {{"intent":"spotify_play_album","action":"spotify_play_album","album":"Fear"}}

    User: Next song
    JSON: {{"intent":"spotify_next","action":"spotify_next"}}

    User: Previous track
    JSON: {{"intent":"spotify_previous","action":"spotify_previous"}}

    User: Resume song
    JSON: {{"intent":"spotify_resume","action":"spotify_resume"}}

    User: Play music
    JSON: {{"intent":"spotify_resume","action":"spotify_resume"}}

    User: Pause the music
    JSON: {{"intent":"spotify_pause","action":"spotify_pause"}}

    User: How are you doing?
    JSON: {{"intent":"conversation","action":"call_llm","text":"How are you doing?"}}

    User: {text}
    JSON:"""
