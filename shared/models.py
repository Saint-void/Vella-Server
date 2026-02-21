# backend/shared/models.py
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from faster_whisper import WhisperModel

# 1. LOAD TINYLLAMA (Shared by Vella & Volco)
LLM_PATH = r"V:\Document\Vella-Modes\models\TinyLlama-1.1B-Chat-v1.0"
print(f"🧠 Loading Global LLM from: {LLM_PATH}...")
tokenizer = AutoTokenizer.from_pretrained(LLM_PATH, local_files_only=True)
model = AutoModelForCausalLM.from_pretrained(LLM_PATH, local_files_only=True)
model.eval()

# 2. LOAD WHISPER (Shared by Web UI & Volco Device)
WHISPER_PATH = r"V:\Document\Vella-Modes\models\models--Systran--faster-whisper-small\snapshots\536b0662742c02347bc0e980a01041f333bce120"
print(f"🎧 Loading Global Whisper from: {WHISPER_PATH}...")
whisper_model = WhisperModel(WHISPER_PATH, device="cpu", compute_type="int8")

print("✅ All Shared Models Loaded Successfully!")