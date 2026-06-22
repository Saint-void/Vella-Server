# backend/shared/models.py
import os
import json
import requests
import torch
from faster_whisper import WhisperModel

try:
    from kokoro_onnx import Kokoro
except ImportError:
    Kokoro = None

# ⚡ APPLE SILICON OPTIMIZATION (M4)
# We let macOS Grand Central Dispatch manage the M4 P-cores and E-cores natively.
max_threads = os.cpu_count() or 4
torch.set_num_threads(max_threads)

# Dynamic path resolution
BASE_MODELS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models"))

# ==========================================
# ⚡ Ollama HTTP Adapter
# ==========================================
OLLAMA_DEFAULT = os.getenv("OLLAMA_DEFAULT_MODEL", "qwen2.5:1.5b")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


class OllamaLLM:
    """Minimal Ollama HTTP adapter exposing a
    `create_chat_completion(..., stream=True)` generator-compatible API
    similar to `llama-cpp-python` so existing callers require minimal changes.
    """

    def __init__(self, default_model: str | None = None, base_url: str | None = None):
        self.default_model = default_model or OLLAMA_DEFAULT
        self.base_url = (base_url or OLLAMA_BASE_URL).rstrip("/")

    def _messages_to_prompt(self, messages: list[dict]) -> str:
        parts = []
        for m in messages:
            role = m.get("role", "user").lower()
            content = m.get("content", "")
            if role == "system":
                parts.append(f"### System:\n{content}\n")
            elif role == "user":
                parts.append(f"### User:\n{content}\n")
            elif role == "assistant":
                parts.append(f"### Assistant:\n{content}\n")
            else:
                parts.append(f"### {role.title()}:\n{content}\n")
        parts.append("### Assistant:\n")
        return "\n".join(parts)

    def create_chat_completion(self, *_, messages: list[dict] | None = None, prompt: str | None = None,
                               model: str | None = None, stream: bool = True,
                               max_tokens: int = 1024, temperature: float = 0.1, **kwargs):
        """Blocking generator that yields chunks matching the llama-cpp `create_chat_completion` stream
        shape: {'choices':[{'delta':{'content': '<token>'}}]}
        """

        model_name = model or self.default_model

        if messages:
            prompt_text = self._messages_to_prompt(messages)
        elif prompt is not None:
            prompt_text = prompt
        else:
            prompt_text = ""

        body = {
            "model": model_name,
            "prompt": prompt_text,
            "max_tokens": max_tokens,
            "temperature": temperature,
            "stream": True
        }

        url = f"{self.base_url}/api/generate"
        resp = requests.post(url, json=body, stream=True, timeout=None)
        resp.raise_for_status()

        for raw in resp.iter_lines(decode_unicode=True):
            if not raw:
                continue
            if isinstance(raw, bytes):
                s = raw.decode("utf-8", errors="replace").strip()
            else:
                s = raw.strip()
            if s.startswith("data:"):
                s = s[len("data:"):].strip()
            token_text = None
            try:
                payload = json.loads(s)
                if isinstance(payload, dict):
                    token_text = payload.get("token") or payload.get("text") or payload.get("response") or payload.get("generated_text")
                    if not token_text and payload.get("choices"):
                        delta = payload["choices"][0].get("delta", {})
                        token_text = delta.get("content")
                else:
                    token_text = str(payload)
            except Exception:
                token_text = s

            if token_text:
                yield {"choices": [{"delta": {"content": token_text}}]}


# Export `llm` for compatibility
llm = OllamaLLM()

# ==========================================
# 2. LOAD WHISPER
# ==========================================
WHISPER_PATH = os.path.join(BASE_MODELS_PATH, "models--deepdml--faster-whisper-large-v3-turbo-ct2")

# CHANGED: 'vocabulary.txt' is now 'vocabulary.json'
WHISPER_REQUIRED_FILES = ("model.bin", "config.json", "tokenizer.json", "vocabulary.json")

missing_whisper_files = [
    filename
    for filename in WHISPER_REQUIRED_FILES
    if not os.path.isfile(os.path.join(WHISPER_PATH, filename))
]

if missing_whisper_files:
    raise FileNotFoundError(
        "Faster-Whisper large-v3-turbo is not fully downloaded. "
        f"Missing {', '.join(missing_whisper_files)} in {WHISPER_PATH}. "
        "Run `Vella-Server/.venv/bin/python Vella/download_stt.py` from /Users/st.void/vella-modes."
    )

print(f"🎧 Loading Global Whisper from: {WHISPER_PATH}...")
whisper_model = WhisperModel(
    WHISPER_PATH, 
    device="cpu", 
    compute_type="int8", # Fixed: int8 is natively supported on the Apple Silicon CPU backend
    cpu_threads=max_threads,
    download_root=None
)

# Optional: Volco can use a smaller Whisper model for low-latency STT.
VOLCO_WHISPER_PATH = os.getenv("VOLCO_WHISPER_PATH", "")
VOLCO_WHISPER_DEVICE = os.getenv("VOLCO_WHISPER_DEVICE", "cpu")
VOLCO_WHISPER_COMPUTE = os.getenv("VOLCO_WHISPER_COMPUTE", "int8")

volco_whisper_model = None
if VOLCO_WHISPER_PATH:
    try:
        print(f"🎧 Loading Volco Whisper from: {VOLCO_WHISPER_PATH}...")
        volco_whisper_model = WhisperModel(
            VOLCO_WHISPER_PATH,
            device=VOLCO_WHISPER_DEVICE,
            compute_type=VOLCO_WHISPER_COMPUTE,
            cpu_threads=max_threads,
            download_root=None,
        )
        print("✅ Volco Whisper loaded.")
    except Exception as e:
        print(f"⚠️ Failed to load Volco Whisper at {VOLCO_WHISPER_PATH}: {e}")
        volco_whisper_model = None

# ==========================================
# 3. LOAD KOKORO TTS WHEN AVAILABLE
# ==========================================
KOKORO_MODEL_DIR = os.path.join(BASE_MODELS_PATH, "kokoro")
KOKORO_ONNX_PATH = os.path.join(KOKORO_MODEL_DIR, "kokoro-v1.0.onnx")
KOKORO_VOICES_PATH = os.path.join(KOKORO_MODEL_DIR, "voices-v1.0.bin")
KOKORO_DEFAULT_VOICE = os.getenv("KOKORO_VOICE", "af_heart")
KOKORO_DEFAULT_SPEED = float(os.getenv("KOKORO_SPEED", "1.2"))
KOKORO_DEFAULT_LANG = os.getenv("KOKORO_LANG", "en-us")

kokoro_voice = None
if Kokoro is not None and os.path.isfile(KOKORO_ONNX_PATH) and os.path.isfile(KOKORO_VOICES_PATH):
    print(f"🗣️ Loading Global Kokoro TTS from: {KOKORO_ONNX_PATH}...")
    kokoro_voice = Kokoro(KOKORO_ONNX_PATH, KOKORO_VOICES_PATH)
else:
    print("⚠️ Kokoro TTS not available. Falling back to Piper TTS.")


print("✅ All Shared Models (Llama-CPP, Whisper, & Piper) Loaded Successfully!")