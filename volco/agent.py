from threading import Thread
from typing import Iterator
from transformers import TextIteratorStreamer

# 👇 Import the shared models
from shared.models import model, tokenizer
from .constants import VOLCO_SYSTEM_INSTRUCTION

def format_chat_prompt(user_message: str):
    messages = [
        {"role": "system", "content": VOLCO_SYSTEM_INSTRUCTION},
        {"role": "user", "content": user_message}
    ]
    return tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

def stream_generate(prompt: str) -> Iterator[str]:
    """Yields tokens from the shared Transformers model."""
    
    formatted_prompt = format_chat_prompt(prompt)
    
    # ⚡ Use the same device as the model
    inputs = tokenizer(formatted_prompt, return_tensors="pt").to(model.device)

    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

    generation_kwargs = dict(
        **inputs,
        streamer=streamer,
        max_new_tokens=120, # Increased for slightly more detailed/soft responses
        pad_token_id=tokenizer.eos_token_id,
        eos_token_id=tokenizer.eos_token_id,
        do_sample=True,
        temperature=0.4,
        top_k=40,
        top_p=0.9,
        repetition_penalty=1.1
    )

    thread = Thread(target=model.generate, kwargs=generation_kwargs)
    thread.start()

    for new_text in streamer:
        yield new_text
