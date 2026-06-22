"""Async-friendly Ollama HTTP client."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import requests

logger = logging.getLogger(__name__)


class OllamaClientError(RuntimeError):
    """Raised when Ollama cannot complete a generation request."""


class OllamaClient:
    """Reusable client for Ollama's `/api/generate` endpoint."""

    def __init__(self, base_url: str | None = None, timeout_seconds: float = 30.0) -> None:
        self.base_url = (base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")).rstrip("/")
        self.timeout_seconds = timeout_seconds

    async def generate(self, model: str, prompt: str) -> str:
        """Generate clean text from an Ollama model."""

        return await asyncio.to_thread(self._generate_sync, model, prompt)

    def _generate_sync(self, model: str, prompt: str) -> str:
        url = f"{self.base_url}/api/generate"
        body: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0,
                "top_p": 0.8,
            },
        }

        try:
            response = requests.post(url, json=body, timeout=self.timeout_seconds)
            response.raise_for_status()
            payload = response.json()
        except requests.Timeout as exc:
            logger.exception("Ollama request timed out.")
            raise OllamaClientError("Ollama request timed out.") from exc
        except requests.ConnectionError as exc:
            logger.exception("Could not connect to Ollama.")
            raise OllamaClientError("Could not connect to Ollama.") from exc
        except requests.RequestException as exc:
            logger.exception("Ollama request failed.")
            raise OllamaClientError(f"Ollama request failed: {exc}") from exc
        except ValueError as exc:
            logger.exception("Ollama returned non-JSON response.")
            raise OllamaClientError("Ollama returned an invalid response.") from exc

        generated = payload.get("response")
        if not isinstance(generated, str):
            raise OllamaClientError("Ollama response did not include generated text.")

        return generated.strip()


async def generate(model: str, prompt: str) -> str:
    """Convenience function matching the project brief."""

    client = OllamaClient()
    return await client.generate(model, prompt)

