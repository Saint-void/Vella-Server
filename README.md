
---

# 🧠 Vella & Volco AI Server (Backend)

> **Local Intelligence Engine for Vella Chat & Volco Voice.**
> *v7.1.0 | FastAPI | PostgreSQL | Piper TTS | Llama-CPP (GGUF) | WebRTC*

The Vella Server is the local backend that powers both the Vella Web Interface and the Volco Hardware/Voice Assistant.

**New in v7.1.0:** 
- **Llama-CPP Integration:** Migrated from `transformers` to `llama-cpp-python` for native GGUF support.
- **Apple Silicon (MPS) Native:** Optimized to run the entire LLM graph on Metal performance shaders (`n_gpu_layers=-1`).
- **Conversational Streaming:** Uses the `create_chat_completion` API for robust, template-free interaction with Gemma 3.
- **Consolidated Model Loading:** Shared `Llama` instance for Vella and Volco.

---

## 🛠️ Core Technology Stack

* **API Framework:** `FastAPI` (Python 3.10+) running on `Uvicorn`.
* **Database:** `PostgreSQL` & `Weaviate`.
* **LLM Engine:** `Gemma 3 1B (GGUF Q4_0)` running via `llama-cpp-python` with **Full MPS (Metal) Acceleration**.
* **Voice Engine:**
  * **STT:** `Faster-Whisper` (Running on optimized CPU int8 for Mac).
  * **TTS:** `Piper TTS` (macOS native binary).
* **Real-Time Comm:** `WebRTC` (aiortc).

---

## 🚀 Quick Start Guide (macOS)

### 1. Prerequisites

* **Python 3.10+**
* **PostgreSQL & Weaviate** installed and running.
* **FFmpeg** installed (`brew install ffmpeg`).
* **Piper macOS Binary:** Place in `../models/piper/piper` and `chmod +x`.

### 2. Installation

```bash
# Create Virtual Environment
python -m venv .venv
source .venv/bin/activate

# Install Dependencies
pip install fastapi uvicorn psycopg2-binary python-dotenv \
            llama-cpp-python faster-whisper weaviate-client \
            sentence-transformers aiortc numpy huggingface_hub
```

### 3. Start the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

---

## 📂 Project Structure

```text
vella-modes/
├── Vella-Server/          # Backend Application (This Repository)
└── models/                # Shared Model Storage
    ├── gemma-3-1b-it-gguf/
    ├── models--Systran--faster-whisper-small/
    └── piper/             # Contains 'piper' binary
```

---

**Developed by Void Tech.** *Private, Local, Intelligent.*
