# backend/vella/agent.py
import torch
from threading import Thread
from typing import List, Dict
from transformers import TextIteratorStreamer

# 👇 Import the shared models and Vella's specific prompt
from shared.models import model, tokenizer
from vella.constants import VELLA_SYSTEM_INSTRUCTION

def format_chat_prompt(messages: List[Dict[str, str]]):
    """
    Expects messages in format: [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}]
    Prepends the system instruction.
    """
    full_messages = [{"role": "system", "content": VELLA_SYSTEM_INSTRUCTION}] + messages
    return tokenizer.apply_chat_template(full_messages, tokenize=False, add_generation_prompt=True)

def stream_generate(messages: List[Dict[str, str]], max_new_tokens: int = 512):
    """
    Generates a response based on the full conversation history.
    """
    formatted_prompt = format_chat_prompt(messages)
    inputs = tokenizer(formatted_prompt, return_tensors="pt").to(model.device)

    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

    generation_kwargs = dict(
        **inputs,
        streamer=streamer,
        max_new_tokens=max_new_tokens,
        pad_token_id=tokenizer.eos_token_id,
        eos_token_id=tokenizer.eos_token_id,
        do_sample=True,
        temperature=0.3,
        top_k=30,
        top_p=0.85,
        repetition_penalty=1.18
    )

    thread = Thread(target=model.generate, kwargs=generation_kwargs)
    thread.start()

    for new_text in streamer:
        yield new_text