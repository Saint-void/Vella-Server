# Vella Server — Backend

> Local backend for the Vella Web UI and the Volco voice device.
> FastAPI | Ollama (HTTP LLM) | Faster-Whisper STT | Kokoro ONNX TTS (optional) | Piper fallback | PostgreSQL + Weaviate | WebRTC

The Vella Server is the unified backend that powers the Vella web interface and the Volco edge device. It exposes REST endpoints for chat, STT and TTS plus Volco-specific routers for device sessions and intent handling.

Key runtime behavior:

- The code uses a small Ollama HTTP adapter by default (`shared/models.py`) — set `OLLAMA_BASE_URL` and `OLLAMA_DEFAULT_MODEL` to point at your LLM backend.
- Faster-Whisper is used for speech-to-text (STT).
- Kokoro ONNX is used for high-quality TTS when `models/kokoro/` is populated; Piper remains a fallback option when Kokoro isn't available.
- The app saves chat history to PostgreSQL and optionally uses Weaviate for semantic memory.

## Core Technology Stack

- API Framework: `FastAPI` (Python 3.10+)
- LLM: Ollama HTTP adapter (default; configurable via `OLLAMA_BASE_URL` / `OLLAMA_DEFAULT_MODEL`)
- STT: `faster-whisper` (global Whisper model)
- TTS: `kokoro-onnx` (optional) with Piper as fallback
- Real-time: `aiortc` (WebRTC)
- Persistence: `PostgreSQL` (chat history) and `Weaviate` (vector memory, optional)

## Quick Start (macOS / Linux)

### 1) Prerequisites

- Python 3.10+
- Ollama (optional but recommended for local LLM hosting) — see https://ollama.com for install instructions
- PostgreSQL & Weaviate (optional, required for persistence and semantic memory)
- FFmpeg (`brew install ffmpeg` on macOS)

### 2) Create a virtualenv and install Python deps

Note: installing `torch` can require platform-specific wheels. Adjust the command for your platform.

```bash
python -m venv .venv
source .venv/bin/activate
pip install fastapi uvicorn python-dotenv requests faster-whisper weaviate-client sentence-transformers aiortc numpy soundfile torch
# Optional: pip install kokoro-onnx piper
```

### 3) Models

- Place model folders under the repository `models/` directory. Examples used by the codebase:
  - `models/models--deepdml--faster-whisper-large-v3-turbo-ct2/` (Whisper)
  - `models/kokoro/` with `kokoro-v1.0.onnx` and `voices-v1.0.bin` (Kokoro TTS)
  - `models/piper/` for a Piper binary (fallback TTS)

Kokoro example (download into `models/kokoro`):

```bash
mkdir -p models/kokoro
curl -L -o models/kokoro/kokoro-v1.0.onnx \
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx
curl -L -o models/kokoro/voices-v1.0.bin \
  https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin
```

### 4) Configuration

- Copy or create `Vella-Server/.env` for local environment variables. Important variables:
  - `OLLAMA_BASE_URL` — URL for the Ollama HTTP server (e.g. `http://127.0.0.1:11434`)
  - `OLLAMA_DEFAULT_MODEL` — default model name used by the adapter
  - `KOKORO_VOICE`, `KOKORO_SPEED`, `KOKORO_LANG` — optional TTS settings

### 5) Start the server

Use the provided helper script which will activate the `Vella-Server/.venv` if present and optionally start Ollama when a local `ollama` binary is available on `PATH`:

```bash
# foreground
./scripts/start_vella.sh

# background
./scripts/start_vella.sh --daemon

# or run directly (with venv activated)
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

The `start_vella.sh` script will try to start Ollama on port `11434` if it's not already running and the `ollama` binary is available on `PATH`.

## Project Structure (overview)

```
vella-modes/
├── Vella-Server/          # Backend application (this folder)
└── models/                # Shared model storage used by server and Volco
    ├── models--deepdml--faster-whisper-large-v3-turbo-ct2/
    ├── models--Systran--faster-whisper-medium.en/
    ├── kokoro/
    │   ├── kokoro-v1.0.onnx
    │   └── voices-v1.0.bin
    └── piper/             # Piper fallback voice model and optional binary
```

## Notes

- The codebase includes an Ollama-compatible adapter so you can use an Ollama HTTP backend or swap in another compatible service.
- If you intend to run entirely on-device (llama-cpp / GGUF), the code can be adapted, but the default provided adapter expects an Ollama-style HTTP API.

## Contributing

- Open issues or PRs for documentation and feature updates. Run tests under `Vella-Server/tests/` and verify hardware-specific changes on target devices.

---

Developed by Void Tech. Private, local, intelligent.
