# backend/chat_agent.py
import os
import torch
from threading import Thread
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

# =============================
# LOCAL MODEL PATH (SHARED)
# =============================
MODEL_PATH = "V:/Document/Vella-Modes/models/TinyLlama-1.1B-Chat-v1.0"

# =============================
# LOAD ONCE (OFFLINE ONLY)
# =============================
print(f"Loading Local Model from: {MODEL_PATH}...")

try:
    tokenizer = AutoTokenizer.from_pretrained(
        MODEL_PATH,
        local_files_only=True
    )

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_PATH,
        local_files_only=True
    )
    
    model.eval()
    print("Model loaded successfully.")

except Exception as e:
    print(f"CRITICAL ERROR LOADING MODEL: {e}")
    raise e

# =============================
# 1. STANDARD GENERATION (For Volco/Voice Mode)
# =============================
def generate(prompt: str, max_new_tokens: int = 128):
    """
    Generates the full text at once. Used for TTS where we need the whole sentence.
    """
    inputs = tokenizer(prompt, return_tensors="pt")

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            pad_token_id=tokenizer.eos_token_id,
            do_sample=True,
            temperature=0.7
        )

    # Only decode the NEW tokens
    prompt_length = inputs.input_ids.shape[1]
    new_tokens = outputs[0][prompt_length:]
    
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()

# =============================
# 2. STREAMING GENERATION (For Chat UI)
# =============================
# In backend/chat_agent.py

def stream_generate(prompt: str, max_new_tokens: int = 128):
    """
    Yields words one by one as they are created.
    """
    inputs = tokenizer([prompt], return_tensors="pt")

    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

    generation_kwargs = dict(
        inputs,
        streamer=streamer,
        max_new_tokens=max_new_tokens,
        pad_token_id=tokenizer.eos_token_id,
        do_sample=True,
        temperature=0.7,
        top_k=50,             # Keeps the AI focused
        top_p=0.95,           # Filters out weird words
        repetition_penalty=1.2  # <--- ADD THIS! (Prevents "download the game" loops)
    )

    thread = Thread(target=model.generate, kwargs=generation_kwargs)
    thread.start()

    for new_text in streamer:
        yield new_text