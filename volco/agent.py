# backend/volco/agent.py
from typing import Iterator
from shared.models import llm
from .constants import VOLCO_SYSTEM_INSTRUCTION

def stream_generate(prompt: str) -> Iterator[str]:
    """Yields tokens from the shared Llama-CPP model via Apple Metal."""
    
    # ⚡ Conversational format for the completion engine
    messages = [
        {"role": "system", "content": VOLCO_SYSTEM_INSTRUCTION},
        {"role": "user", "content": prompt}
    ]

    # ⚡ CHAT COMPLETION SYNTAX
    response_stream = llm.create_chat_completion(
        messages=messages, # type: ignore
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
