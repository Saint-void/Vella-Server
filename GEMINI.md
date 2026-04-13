# 🧠 Vella & Volco AI Server - Project Documentation

This project is a high-performance, local AI backend powering the **Vella** (Web/Text) and **Volco** (Voice/Hardware) assistants. It leverages state-of-the-art local models for LLM inference, STT, and TTS.

## 🏗️ Architecture & Core Technologies

The server is built with a modular "Dual-Persona" architecture, allowing two distinct AI personas to share a single LLM instance to optimize VRAM usage.

- **API Framework:** FastAPI (running on Uvicorn, port 8001).
- **Primary Database:** PostgreSQL (Users, Sessions, Chat History).
- **Vector Database:** Weaviate (Long-term semantic memory).
- **LLM Engine:**
  - **Gemma 3 1B GGUF (Q4_0):** Shared by both personas. Uses highly-optimized 4-bit quantization for superior speed and memory efficiency.
  - **Vella (Text):** High-quality, long-form streaming.
  - **Volco (Voice):** Low-latency, short-form responses.
- **Voice Stack:**
  - **STT:** `Faster-Whisper` (small model, float16/int8 quantization).
  - **TTS:** `Piper TTS` (ONNX) for near-instant local raw PCM synthesis.
- **Communication:**
  - **REST:** Standard chat and authentication.
  - **WebRTC:** Ultra-low latency audio streaming and data signaling for Volco.

## 📂 Directory Structure

- `main.py`: Entry point, FastAPI app configuration, and Web UI endpoints.
- `db.py`: PostgreSQL connection management, schema initialization, and message persistence.
- `auth.py`: Authentication logic (Register/Login).
- `vector_store.py`: Weaviate integration and semantic search logic (Long-term Memory).
- `shared/`: Shared resources.
  - `models.py`: Centralized model loading (TinyLlama & Whisper) to prevent redundant VRAM usage. GPU-optimized.
- `vella/`: Logic for the Web/Text assistant.
  - `agent.py`: `transformers`-based streaming generation (Long-form).
  - `constants.py`: Vella's system prompt and persona rules.
- `volco/`: Logic for the Voice/Hardware assistant.
  - `agent.py`: `transformers`-based fast generation (Short-form).
  - `router.py`: WebRTC signaling, PCM audio chunking, and interrupt handling.
  - `action_engine.py`: Local command execution (Spotify, Time, Date).
  - `connection.py`: Management of active voice connections.

## 🚀 Building and Running

### Prerequisites
- Python 3.10+
- PostgreSQL (running locally)
- Weaviate (running on port 8080)
- FFmpeg (for audio processing)
- Local model files (TinyLlama, Whisper, Piper ONNX) in the configured paths.

### Installation
```bash
# Create and activate virtual environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install dependencies
pip install fastapi uvicorn psycopg2-binary python-dotenv transformers torch \
            faster-whisper weaviate-client sentence-transformers \
            aiortc numpy
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

1. **Model Loading:** Never load LLM or Whisper models outside of `shared/models.py`. Use the shared instances to avoid memory exhaustion.
2. **Streaming:** Always use `StreamingResponse` for LLM outputs in the Web UI. For Volco, use the WebRTC data channel for PCM audio chunks and JSON commands.
3. **Audio Handling:** Volco uses a "Paced Chunker" (`send_pcm_in_chunks`) to stream raw PCM data over WebRTC to ensure smooth playback on hardware devices.
4. **VAD:** Voice Activity Detection is handled client-side. The server expects a `COMMIT` signal over the WebRTC data channel to trigger transcription and response.
5. **Interrupts:** Voice interactions support immediate interruption. When an `INTERRUPT` signal is received, `user_interrupt_flags` are set to kill LLM generation and PCM streaming instantly.
6. **Database & Memory:** Every interaction (Text or Voice) must be saved to PostgreSQL via `save_message()` and to Weaviate via `add_memory()`.
