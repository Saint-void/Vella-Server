# 🧠 Vella & Volco AI Server - Project Documentation

This project is a high-performance, local AI backend powering the **Vella** (Web/Text) and **Volco** (Voice/Hardware) assistants. It leverages state-of-the-art local models for LLM inference, STT, and TTS.

## 🏗️ Architecture & Core Technologies

The server is built with a modular "Dual-Persona" architecture, allowing two distinct AI personas to share a single LLM instance to optimize VRAM usage.

- **API Framework:** FastAPI (running on Uvicorn, port 8001).
- **Primary Database:** PostgreSQL (Users, Sessions, Chat History).
- **Vector Database:** Weaviate (Long-term semantic memory).
- **LLM Engine:**
  - **Gemma 3 1B GGUF (Q4_0):** Shared by both personas. 
  - **Inference Engine:** `llama-cpp-python` (Llama-CPP).
  - **Hardware Acceleration:** **Optimized for Apple Silicon (MPS)** using `n_gpu_layers=-1` to run the entire graph on Metal Performance Shaders.
- **Voice Stack:**
  - **STT:** `Faster-Whisper` (small model). Runs on CPU (int8) for macOS.
  - **TTS:** `Piper TTS` (ONNX) for near-instant local raw PCM synthesis. **Uses macOS-native binary.**

## 📂 Directory Structure & Models

The server expects a sibling `models/` folder in the parent directory:
```
vella-modes/
├── Vella-Server/  (This Repository)
└── models/        (Model Files)
    ├── gemma-3-1b-it-gguf/
    ├── models--Systran--faster-whisper-small/
    ├── piper/ (macOS binary named 'piper')
    └── tts-piper/
```

## 🚀 Building and Running (macOS)

### Prerequisites
- Python 3.10+
- PostgreSQL & Weaviate
- **Piper macOS Binary:** Download the macOS version of Piper and place it in `../models/piper/piper`. Make it executable: `chmod +x ../models/piper/piper`.

### Installation
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install fastapi uvicorn psycopg2-binary python-dotenv \
            llama-cpp-python faster-whisper weaviate-client \
            sentence-transformers aiortc numpy huggingface_hub
```

### Configuration
Create a `.env` file in the root:
```env
DATABASE_URL="postgresql://postgres:password@localhost:5432/vella"
SECRET_KEY="your_secret_key"
```

### Execution
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

## 🛠️ Development Conventions

1. **Model Loading:** Never load LLM or Whisper models outside of `shared/models.py`. Use the shared `llm` (Llama instance) to avoid memory exhaustion.
2. **LLM Interaction:** Use `llm.create_chat_completion(messages=[...], stream=True)` for all AI responses. Do not use `transformers` or manual text templating.
3. **Streaming:** Always use `StreamingResponse` for LLM outputs in the Web UI. For Volco, use the WebRTC data channel for PCM audio chunks and JSON commands.
4. **Audio Handling:** Volco uses a "Paced Chunker" (`send_pcm_in_chunks`) to stream raw PCM data over WebRTC to ensure smooth playback on hardware devices.
5. **Interrupts:** Voice interactions support immediate interruption. When an `INTERRUPT` signal is received, `user_interrupt_flags` are set to kill LLM generation and PCM streaming instantly.
6. **Database & Memory:** Every interaction (Text or Voice) must be saved to PostgreSQL via `save_message()` and to Weaviate via `add_memory()`.
