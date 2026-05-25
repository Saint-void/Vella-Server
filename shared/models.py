# backend/shared/models.py
import os
import torch
from llama_cpp import Llama
from faster_whisper import WhisperModel
from piper import PiperVoice  # 👈 Clean Python Import

# ⚡ CPU OPTIMIZATION: Set threads to avoid resource contention
num_threads = (os.cpu_count() or 1) // 2 or 1
torch.set_num_threads(num_threads)

# Dynamic path resolution
BASE_MODELS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models"))

# 1. LOAD GEMMA 3 1B GGUF via llama-cpp-python
LLM_PATH = os.path.join(BASE_MODELS_PATH, "gemma-3-1b-it-gguf")
GGUF_FILE = "gemma-3-1b-it-q4_0.gguf"
MODEL_PATH = os.path.join(LLM_PATH, GGUF_FILE)

print(f"🧠 Loading Global LLM (Gemma 3 GGUF) from: {MODEL_PATH} onto Apple Metal (MPS)...")
llm = Llama(
    model_path=MODEL_PATH,
    n_gpu_layers=-1,
    n_ctx=4096,
    verbose=False
)

# 2. LOAD WHISPER
WHISPER_PATH = os.path.join(BASE_MODELS_PATH, "models--Systran--faster-whisper-small")
print(f"🎧 Loading Global Whisper from: {WHISPER_PATH}...")
whisper_model = WhisperModel(
    WHISPER_PATH, 
    device="cpu", 
    compute_type="int8",
    cpu_threads=num_threads,
    download_root=None
)

# ==========================================
# 3. LOAD PIPER TTS NATIVELY (NEW)
# ==========================================
# Ensure this folder name matches your voice model's directory name inside models/
PIPER_MODEL_DIR = os.path.join(BASE_MODELS_PATH, "piper")

# Find the first .onnx file inside the directory automatically
onnx_files = [f for f in os.listdir(PIPER_MODEL_DIR) if f.endswith('.onnx')] if os.path.exists(PIPER_MODEL_DIR) else []

if not onnx_files:
    raise FileNotFoundError(f"❌ Could not find an .onnx model file inside: {PIPER_MODEL_DIR}")

PIPER_ONNX_PATH = os.path.join(PIPER_MODEL_DIR, onnx_files[0])
PIPER_CONFIG_PATH = PIPER_ONNX_PATH + ".json"

print(f"🗣️ Loading Global Piper TTS from: {PIPER_ONNX_PATH}...")
piper_voice = PiperVoice.load(PIPER_ONNX_PATH, config_path=PIPER_CONFIG_PATH)

print("✅ All Shared Models (Llama-CPP, Whisper, & Piper) Loaded Successfully!")
