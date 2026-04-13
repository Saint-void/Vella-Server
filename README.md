
---

# 🧠 Vella & Volco AI Server (Backend)

> **Local Intelligence Engine for Vella Chat & Volco Voice.**
> *v7.0.0 | FastAPI | PostgreSQL | Piper TTS | Faster-Whisper | WebRTC*

The Vella Server is the local backend that powers both the Vella Web Interface and the Volco Hardware/Voice Assistant. It handles LLM inference, voice processing (STT/TTS), action execution, and features **Persistent Long-Term Memory** via PostgreSQL and Weaviate.

**New in v7.0.0:** 
- **Upgraded to Gemma 3 1B (GGUF):** Switched to the state-of-the-art Gemma 3 1B model, specifically the QAT Q4_0 quantized GGUF version. This provides significantly higher intelligence than TinyLlama while being faster and using less memory.
- **Consolidated Model Loading:** Vella and Volco now share a single Gemma 3 GGUF instance (via Transformers) to drastically reduce resource usage.
- **WebRTC for Voice:** Replaced standard WebSockets with WebRTC for Volco's voice streaming to ensure ultra-low latency and robust real-time communication.
- **Client-Side VAD:** Voice Activity Detection (VAD) is now offloaded to the Volco client, ensuring the server only processes audio when a complete thought is captured.
- **Persistent Memory:** Every voice and text interaction is automatically saved to PostgreSQL (history) and Weaviate (semantic retrieval).

---

## 🛠️ Core Technology Stack

* **API Framework:** `FastAPI` (Python 3.10+) running on `Uvicorn`.
* **Database:** `PostgreSQL` — *Stores Users, Sessions, and Message Logs.*
* **LLM Engine:** `Gemma 3 1B (GGUF Q4_0)` (Shared) running via `Transformers` with `gguf` acceleration.
* **Voice Engine:**
  * **STT:** `Faster-Whisper` (Small model, optimized with VAD filter).
  * **TTS:** `Piper TTS` (Zero-latency local raw PCM synthesis).
* **Real-Time Comm:** `WebRTC` (aiortc) — For high-performance, low-latency audio and data channels.
* **Action Engine:** Custom command parser for Spotify control, system time, and more.
* **Memory:** `Weaviate` — Vector database for semantic context retrieval.

---

## 🚀 Quick Start Guide

### 1. Prerequisites

* **Python 3.10+**
* **PostgreSQL** installed and running locally.
* **FFmpeg** installed and added to system PATH.
* **Weaviate** running locally (Port 8080).
* **CUDA Toolkit** (Optional, for GPU acceleration).

### 2. Database Configuration

Create a `.env` file in the root directory:

```env
DATABASE_URL="postgresql://postgres:password@localhost:5432/vella"
SECRET_KEY="supersecretkey"
```

### 3. Installation

```bash
# Create Virtual Environment
python -m venv .venv
source .venv/bin/activate  # or .venv\Scripts\activate on Windows

# Install Dependencies
pip install fastapi uvicorn psycopg2-binary python-dotenv transformers torch \
            faster-whisper weaviate-client sentence-transformers aiortc numpy
```

### 4. Start the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

---

## 📂 Project Structure

```text
VELLA-SERVER/
├── main.py                # Entry point (FastAPI App & Startup Logic)
├── db.py                  # Postgres Connection & Schema Management
├── auth.py                # User Authentication (Register/Login)
├── vector_store.py        # Weaviate Vector Memory Logic
├── .env                   # Environment Variables
│
├── shared/                # 🧠 THE SHARED BRAIN
│   └── models.py          # Centralized LLM & Whisper Loading (GPU Optimized)
│
├── vella/                 # 🌌 VELLA (Web/Text Assistant)
│   ├── constants.py       # Vella's Persona Rules
│   └── agent.py           # Long-form streaming agent
│
└── volco/                 # 🗣️ VOLCO (Voice/Hardware Assistant)
    ├── agent.py           # Short-form, fast voice agent
    ├── router.py          # WebRTC Signaling & Voice Brain
    ├── connection.py      # Real-time state management
    ├── action_engine.py   # Spotify & System Command execution
    └── db.py              # Volco-specific DB helpers
```

---

## 🔌 Primary API & Real-Time Endpoints

### **Vella (Text)**
* `POST /chat` — Stream LLM responses for the Web UI.

### **Volco (Voice)**
* `POST /volco_webrtc/offer` — WebRTC signaling endpoint for high-speed voice and data.
* `POST /api/volco/login` — Dedicated mobile/hardware login endpoint.

### **History & Memory**
* `GET /history/sessions` — Get all chat sessions for a user.
* `GET /history/{session_id}` — Get full message history.

---

**Developed by Void Tech.** *Private, Local, Intelligent.*
