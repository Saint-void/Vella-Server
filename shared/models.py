# backend/shared/models.py
import os
import torch
from llama_cpp import Llama
from faster_whisper import WhisperModel
from piper import PiperVoice  # 👈 Clean Python Import

try:
    from kokoro_onnx import Kokoro
except ImportError:
    Kokoro = None

# ⚡ CPU OPTIMIZATION: Set threads to avoid resource contention
num_threads = (os.cpu_count() or 1) // 2 or 1
torch.set_num_threads(num_threads)

# Dynamic path resolution
BASE_MODELS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models"))

# 1. LOAD GEMMA 3 4B GGUF via llama-cpp-python
LLM_PATH = os.path.join(BASE_MODELS_PATH, "gemma-3-4b-it-gguf")
GGUF_FILE = "google_gemma-3-4b-it-Q4_K_M.gguf"
MODEL_PATH = os.path.join(LLM_PATH, GGUF_FILE)

if not os.path.isfile(MODEL_PATH):
    raise FileNotFoundError(
        f"Gemma model file not found at {MODEL_PATH}. "
        "Make sure the Gemma 3 4B GGUF is present in the local models folder."
    )

print(f"🧠 Loading Global LLM (Gemma 3 4B GGUF) from: {MODEL_PATH} onto Apple Metal (MPS)...")
llm = Llama(
    model_path=MODEL_PATH,
    n_gpu_layers=-1,
    n_ctx=4096,
    verbose=False
)

# 2. LOAD WHISPER
WHISPER_PATH = os.path.join(BASE_MODELS_PATH, "models--Systran--faster-whisper-medium.en")
WHISPER_REQUIRED_FILES = ("model.bin", "config.json", "tokenizer.json", "vocabulary.txt")
missing_whisper_files = [
    filename
    for filename in WHISPER_REQUIRED_FILES
    if not os.path.isfile(os.path.join(WHISPER_PATH, filename))
]

if missing_whisper_files:
    raise FileNotFoundError(
        "Faster-Whisper medium.en is not fully downloaded. "
        f"Missing {', '.join(missing_whisper_files)} in {WHISPER_PATH}. "
        "Run `Vella-Server/.venv/bin/python Vella/download_stt.py` from /Users/st.void/vella-modes."
    )

print(f"🎧 Loading Global Whisper from: {WHISPER_PATH}...")
whisper_model = WhisperModel(
    WHISPER_PATH, 
    device="cpu", 
    compute_type="int8",
    cpu_threads=num_threads,
    download_root=None
)

# ==========================================
# 3. LOAD KOKORO TTS WHEN AVAILABLE
# ==========================================
KOKORO_MODEL_DIR = os.path.join(BASE_MODELS_PATH, "kokoro")
KOKORO_ONNX_PATH = os.path.join(KOKORO_MODEL_DIR, "kokoro-v1.0.onnx")
KOKORO_VOICES_PATH = os.path.join(KOKORO_MODEL_DIR, "voices-v1.0.bin")
KOKORO_DEFAULT_VOICE = os.getenv("KOKORO_VOICE", "af_nova")
KOKORO_DEFAULT_SPEED = float(os.getenv("KOKORO_SPEED", "1.0"))
KOKORO_DEFAULT_LANG = os.getenv("KOKORO_LANG", "en-us")

kokoro_voice = None
if Kokoro is not None and os.path.isfile(KOKORO_ONNX_PATH) and os.path.isfile(KOKORO_VOICES_PATH):
    print(f"🗣️ Loading Global Kokoro TTS from: {KOKORO_ONNX_PATH}...")
    kokoro_voice = Kokoro(KOKORO_ONNX_PATH, KOKORO_VOICES_PATH)
else:
    print("⚠️ Kokoro TTS not available. Falling back to Piper TTS.")

# ==========================================
# 4. LOAD PIPER TTS NATIVELY (FALLBACK / VOLCO)
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
