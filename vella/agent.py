# backend/vella/agent.py
import torch
from threading import Thread
from transformers import TextIteratorStreamer

# 👇 Import the shared models and Vella's specific prompt
from shared.models import model, tokenizer
from vella.constants import VELLA_SYSTEM_INSTRUCTION

def format_chat_prompt(user_message: str):
    messages = [
        {"role": "system", "content": VELLA_SYSTEM_INSTRUCTION},
        {"role": "user", "content": user_message}
    ]
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

def stream_generate(prompt: str, max_new_tokens: int = 512):
    formatted_prompt = format_chat_prompt(prompt)
    inputs = tokenizer(formatted_prompt, return_tensors="pt")

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