# backend/vella/agent.py
from typing import List, Dict
import os
from shared.models import llm
from vella.constants import VELLA_SYSTEM_INSTRUCTION

# Default Ollama model for Vella (high-thinking)
OLLAMA_VELLA_DEFAULT = os.getenv("OLLAMA_VELLA_DEFAULT_MODEL", "qwen2.5:7b")

def stream_generate(messages: List[Dict[str, str]], max_new_tokens: int = 2048, model: str | None = None):
    """
    Generates a response using llama-cpp-python's create_chat_completion.
    """

    # ⚡ Prepends the system instruction
    full_messages = [{"role": "system", "content": VELLA_SYSTEM_INSTRUCTION}] + messages

    # Choose model: explicit argument > env default
    model_name = model or OLLAMA_VELLA_DEFAULT

    # ⚡ CHAT COMPLETION SYNTAX: Conversational streaming
    response_stream = llm.create_chat_completion(
        messages=full_messages,  # type: ignore
        model=model_name,
        stream=True,
        max_tokens=max_new_tokens,
        temperature=0.1,
        top_k=30,
        top_p=0.85,
        repeat_penalty=1.18
    )

    for chunk in response_stream:
        # Extract the token content from the delta properly
        if "choices" in chunk and chunk["choices"]:
            delta = chunk["choices"][0].get("delta", {})
            if "content" in delta:
                yield delta["content"]
