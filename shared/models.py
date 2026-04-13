# backend/shared/models.py
import torch
import os
from transformers import AutoModelForCausalLM, AutoTokenizer
from faster_whisper import WhisperModel

# ⚡ CPU OPTIMIZATION: Set threads to avoid resource contention
# Usually, physical core count is best.
num_threads = os.cpu_count() // 2 or 1
torch.set_num_threads(num_threads)

# 1. LOAD GEMMA 3 1B GGUF (Shared by Vella & Volco)
LLM_PATH = r"V:\Document\Vella-Modes\models\gemma-3-1b-it-gguf"
# GGUF file name inside that folder (updated based on actual file name)
GGUF_FILE = "gemma-3-1b-it-q4_0.gguf"

device = "cuda" if torch.cuda.is_available() else "cpu"
print(f"🧠 Loading Global LLM (Gemma 3 GGUF) from: {LLM_PATH} onto {device}...")

# Use the LLM_PATH directory for the tokenizer, explicitly allowing the slow version.
tokenizer = AutoTokenizer.from_pretrained(LLM_PATH, local_files_only=True, use_fast=False)
# For GGUF files with transformers, we point to the directory and specify the gguf_file.
# This requires the 'gguf' package (pip install gguf).
model = AutoModelForCausalLM.from_pretrained(
    LLM_PATH, 
    gguf_file=GGUF_FILE,
    local_files_only=True,
    device_map=device
)
model.eval()

# 2. LOAD WHISPER (Shared by Web UI & Volco Device)
# Using 'small' might be heavy for CPU, but we'll optimize the thread count.
WHISPER_PATH = r"V:\Document\Vella-Modes\models\models--Systran--faster-whisper-small\snapshots\536b0662742c02347bc0e980a01041f333bce120"
print(f"🎧 Loading Global Whisper from: {WHISPER_PATH}...")
whisper_model = WhisperModel(
    WHISPER_PATH, 
    device="cpu", 
    compute_type="int8",
    cpu_threads=num_threads, # ⚡ Use optimized thread count
    download_root=None
)

print("✅ All Shared Models Loaded Successfully!")