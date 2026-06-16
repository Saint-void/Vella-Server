# backend/volco/agent.py
from typing import Iterator
import os
from shared.models import llm
from .constants import VOLCO_SYSTEM_INSTRUCTION

# Default Ollama model for Volco (lightweight conversational)
OLLAMA_VOLCO_DEFAULT = os.getenv("OLLAMA_VOLCO_DEFAULT_MODEL", "qwen3:1.7b")


def stream_generate(prompt: str, model: str | None = None) -> Iterator[str]:
    """Yields tokens from Ollama via the shared adapter."""
    model_name = model or OLLAMA_VOLCO_DEFAULT

    messages = [
        {"role": "system", "content": VOLCO_SYSTEM_INSTRUCTION},
        {"role": "user", "content": prompt}
    ]

    response_stream = llm.create_chat_completion(
        messages=messages,  # type: ignore
        model=model_name,
        stream=True,
        max_tokens=1000,
        temperature=0.4,
        top_k=40,
        top_p=0.9,
        repeat_penalty=1.1
    )

    for chunk in response_stream:
        if "choices" in chunk and len(chunk["choices"]) > 0:
            delta = chunk["choices"][0].get("delta", {})
            if "content" in delta:
                yield delta["content"]
