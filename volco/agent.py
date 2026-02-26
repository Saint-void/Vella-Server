import torch
from threading import Thread
from transformers import TextIteratorStreamer

# ⚡ IMPORT ALREADY LOADED MODELS FROM SHARED
from shared.models import model, tokenizer

def stream_generate(prompt: str):
    """Yields words one by one, strictly formatted for short voice replies."""
    
    # TinyLlama Chat Format + Strict System Rule
    system_prompt = "You are Volco, a voice assistant. Answer in exactly one short sentence."
    final_prompt = f"<|system|>\n{system_prompt}</s>\n<|user|>\n{prompt}</s>\n<|assistant|>\n"
    
    inputs = tokenizer([final_prompt], return_tensors="pt")
    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

    generation_kwargs = dict(
        **inputs,
        streamer=streamer,
        max_new_tokens=40,      # Strict limit for voice
        pad_token_id=tokenizer.eos_token_id,
        do_sample=True,
        temperature=0.7,
        top_k=50,
        top_p=0.95,
        repetition_penalty=1.2
    )

    thread = Thread(target=model.generate, kwargs=generation_kwargs)
    thread.start()

    for new_text in streamer:
        # Early cutoff: Stop if it tries to hallucinate a new line
        if "\n" in new_text:
            yield new_text.split("\n")[0]
            break
        yield new_text