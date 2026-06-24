# backend/shared/models.py
import os
import json
import requests
import torch

try:
    import mlx_whisper
    MLX_AVAILABLE = True
except ImportError:
    MLX_AVAILABLE = False
    print("⚠️ mlx-whisper not installed. Run: pip install mlx-whisper")

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
# 2. MLX WHISPER WRAPPER
# ==========================================
# MLX Whisper uses Apple's MLX framework — runs on the M4 GPU/Neural Engine
# instead of CPU. No model files needed locally; mlx-whisper downloads and
# caches MLX-format models from HuggingFace automatically on first use.
#
# HF repo mappings:
#   tiny.en   → mlx-community/whisper-tiny.en-mlx
#   small.en  → mlx-community/whisper-small.en-mlx
#   medium.en → mlx-community/whisper-medium.en-mlx
#   large-v3-turbo → mlx-community/whisper-large-v3-turbo
#
# Override via env vars:
#   WHISPER_MLX_REPO      — main Vella STT model (default: small.en)
#   VOLCO_WHISPER_MLX_REPO — Volco STT model (default: tiny.en for low latency)

WHISPER_MLX_REPO = os.getenv("WHISPER_MLX_REPO", "mlx-community/whisper-medium.en-mlx")
VOLCO_WHISPER_MLX_REPO = os.getenv("VOLCO_WHISPER_MLX_REPO", "mlx-community/whisper-small.en-mlx")


class MLXWhisperModel:
    """
    Thin wrapper around mlx_whisper.transcribe() that mimics the
    faster-whisper WhisperModel.transcribe() return signature so existing
    callers need zero changes:

        segments, info = whisper_model.transcribe(audio_path)
        for seg in segments:
            print(seg.text)
    """

    def __init__(self, repo: str):
        self.repo = repo
        print(f"🎧 MLX Whisper ready — model: {repo} (GPU/Neural Engine)")

    def transcribe(self, audio, language: str = "en", **kwargs):
        # Strip faster-whisper-only kwargs that mlx_whisper doesn't support
        kwargs.pop("vad_filter", None)
        kwargs.pop("vad_parameters", None)
        kwargs.pop("beam_size", None)

        result = mlx_whisper.transcribe(
            audio,
            path_or_hf_repo=self.repo,
            language=language,
            fp16=True,         # fp16 is faster on Apple Silicon
            **kwargs,
        )

        # Build a segments list that matches faster-whisper's SimpleNamespace shape
        class _Seg:
            def __init__(self, d):
                self.id = d.get("id", 0)
                self.start = d.get("start", 0.0)
                self.end = d.get("end", 0.0)
                self.text = d.get("text", "")
                self.words = d.get("words", [])

        class _Info:
            language = "en"
            language_probability = 1.0

        segments = [_Seg(s) for s in result.get("segments", [])]

        # If no segments but we have top-level text, wrap it
        if not segments and result.get("text"):
            segments = [_Seg({"text": result["text"], "start": 0.0, "end": 0.0})]

        return segments, _Info()


if not MLX_AVAILABLE:
    raise ImportError(
        "mlx-whisper is required for Apple Silicon GPU acceleration. "
        "Install it with: pip install mlx-whisper"
    )

print(f"🎧 Loading Vella Whisper (MLX) — repo: {WHISPER_MLX_REPO}")
whisper_model = MLXWhisperModel(WHISPER_MLX_REPO)

# Volco gets a tinier, faster model for low-latency real-time STT
print(f"🎧 Loading Volco Whisper (MLX) — repo: {VOLCO_WHISPER_MLX_REPO}")
volco_whisper_model = MLXWhisperModel(VOLCO_WHISPER_MLX_REPO)


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


print("✅ All Shared Models (Ollama, MLX Whisper, Kokoro) Loaded Successfully!")