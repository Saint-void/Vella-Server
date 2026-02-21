# backend/volco/agent.py
import torch
from threading import Thread
from transformers import TextIteratorStreamer
from shared.models import model, tokenizer

VOLCO_SYSTEM_INSTRUCTION = "You are Volco, a helpful voice assistant. Reply very briefly and naturally."

def format_chat_prompt(user_message: str):
    messages = [
        {"role": "system", "content": VOLCO_SYSTEM_INSTRUCTION},
        {"role": "user", "content": user_message}
    ]
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

def stream_generate(prompt: str, max_new_tokens: int = 40):
    formatted_prompt = format_chat_prompt(prompt)
    inputs = tokenizer(formatted_prompt, return_tensors="pt")

    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

    generation_kwargs = dict(
        **inputs,
        streamer=streamer,
        max_new_tokens=max_new_tokens,
        pad_token_id=tokenizer.eos_token_id,
        eos_token_id=tokenizer.eos_token_id,
        do_sample=False, 
        repetition_penalty=1.15
    )

    thread = Thread(target=model.generate, kwargs=generation_kwargs)
    thread.start()

    for new_text in streamer:
        # Force cut off at the first newline so Volco doesn't ramble
        if "\n" in new_text:
            yield new_text.split("\n")[0]
            break
        yield new_text