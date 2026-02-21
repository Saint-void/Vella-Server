import os
import torch
from threading import Thread
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

# =============================
# LOCAL MODEL PATH
# =============================
MODEL_PATH = r"V:\Document\Vella-Modes\models\TinyLlama-1.1B-Chat-v1.0"

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
# FORMAT CHAT PROMPT (FIX)
# =============================
def format_chat_prompt(user_message: str, is_voice: bool = False):

    if is_voice:
        system_message = "You are Volco, a helpful voice assistant. Reply very briefly and naturally."
    else:
        system_message = "You are a helpful, concise assistant."

    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": user_message}
    ]

    formatted_prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    return formatted_prompt


# =============================
# STANDARD GENERATION
# =============================
def generate(prompt: str, max_new_tokens: int = 128, is_voice: bool = False):

    if is_voice:
        max_new_tokens = 40

    formatted_prompt = format_chat_prompt(prompt, is_voice)

    inputs = tokenizer(formatted_prompt, return_tensors="pt")

    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=max_new_tokens,
            pad_token_id=tokenizer.eos_token_id,
            do_sample=True,
            temperature=0.0,
            top_k=40,
            top_p=0.9,
            repetition_penalty=1.1
        )

    prompt_length = inputs.input_ids.shape[1]
    new_tokens = outputs[0][prompt_length:]

    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


# =============================
# STREAMING GENERATION
# =============================
def stream_generate(prompt: str, max_new_tokens: int = 128, is_voice: bool = False):

    if is_voice:
        max_new_tokens = 40

    formatted_prompt = format_chat_prompt(prompt, is_voice)

    inputs = tokenizer([formatted_prompt], return_tensors="pt")

    streamer = TextIteratorStreamer(
        tokenizer,
        skip_prompt=True,
        skip_special_tokens=True
    )

    generation_kwargs = dict(
        **inputs,
        streamer=streamer,
        max_new_tokens=max_new_tokens,
        pad_token_id=tokenizer.eos_token_id,
        do_sample=True,
        temperature=0.3,
        top_k=40,
        top_p=0.9,
        repetition_penalty=1.1
    )

    thread = Thread(target=model.generate, kwargs=generation_kwargs)
    thread.start()

    for new_text in streamer:

        if is_voice and "\n" in new_text:
            yield new_text.split("\n")[0]
            break

        yield new_text
