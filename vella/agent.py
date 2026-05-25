# backend/vella/agent.py
from typing import List, Dict
from shared.models import llm
from vella.constants import VELLA_SYSTEM_INSTRUCTION

def stream_generate(messages: List[Dict[str, str]], max_new_tokens: int = 512):
    """
    Generates a response using llama-cpp-python's create_chat_completion.
    Natively handles the Gemma-3 chat template.
    """

    # ⚡ Prepends the system instruction
    full_messages = [{"role": "system", "content": VELLA_SYSTEM_INSTRUCTION}] + messages

    # ⚡ CHAT COMPLETION SYNTAX: Conversational streaming
    response_stream = llm.create_chat_completion(
        messages=full_messages,  # type: ignore
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
