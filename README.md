
---

# 🧠 Vella & Volco AI Server (Backend)

> **Local Intelligence Engine for Vella Chat & Volco Voice.**
> *v6.0.0 | FastAPI | PostgreSQL | Piper TTS | Faster-Whisper | WebSockets*

The Vella Server is the local backend that powers both the Vella Web Interface and the Volco Hardware/Voice Assistant. It handles LLM inference, voice processing (STT/TTS), action execution, and features **Persistent Long-Term Memory** via PostgreSQL and Weaviate.

**New in v6.0.0:** A complete architectural rewrite introducing a **Dual-Persona Modular System**. Vella (long-form text) and Volco (real-time voice) now run on separate logic streams while sharing a single LLM loaded in memory to prevent VRAM exhaustion. Added WebSocket support for instant audio streaming.

---

## 🛠️ Core Technology Stack

* **API Framework:** `FastAPI` (Python 3.10+) running on `Uvicorn`.
* **Database:** `PostgreSQL` — *Stores Users, Sessions, and Message Logs.*
* **LLM Engine:** `TinyLlama 1.1B` running via `Transformers` with `TextIteratorStreamer`.
* **Voice Engine:**
* **STT:** `Faster-Whisper` (Local, GPU/Float16 optimized with CPU/Int8 fallback).
* **TTS:** `Piper TTS` (Zero-latency local raw PCM & WAV synthesis).


* **Real-Time Comm:** `WebSockets` — For continuous two-way audio streaming (Volco).
* **Action Engine:** Custom command parser for opening apps, playing music, and checking system time.
* **Memory:** `Weaviate` — Vector database for semantic context retrieval.

---

## 🚀 Quick Start Guide

### 1. Prerequisites

* **Python 3.10+**
* **PostgreSQL** installed and running locally.
* **FFmpeg** installed and added to system PATH.
* **Weaviate** running locally (Port 8080).

### 2. Database Configuration

Create a `.env` file in the `backend/` directory or ensure your `db.py` defaults match your local Postgres setup:

```env
# Example .env configuration
DATABASE_URL="postgresql://postgres:password@localhost:5432/vella"
SECRET_KEY="supersecretkey"

```

*Note: The server will automatically create the necessary tables (`users`, `sessions`, `messages`) on the first run.*

### 3. Installation

```bash
# Create Virtual Environment
python -m venv venv

# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate

# Install Dependencies
pip install fastapi uvicorn psycopg2-binary python-dotenv transformers torch faster-whisper weaviate-client sentence-transformers

```

### 4. Start the Server

Run the server using Uvicorn on **Port 8001**:

```bash
# Run with auto-reload for development
uvicorn main:app --reload --host 0.0.0.0 --port 8001

```

---

## 📂 Project Structure (Modular Architecture)

```text
VELLA-SERVER/
├── main.py                # Entry point (FastAPI App, Routes, & Startup Logic)
├── db.py                  # Database Connection & Schema Initialization (Postgres)
├── auth.py                # User Authentication (Register/Login Endpoints)
├── action_engine.py       # Executes local system commands (Time, Apps, Browser)
├── vector_store.py        # Weaviate Connection for Semantic Memory
├── .env                   # Environment Variables
│
├── shared/                # 🧠 THE SHARED BRAIN
│   ├── __init__.py
│   └── models.py          # Loads TinyLlama & Whisper ONCE to save RAM
│
├── vella/                 # 🌌 VELLA'S LOGIC (Web/Text)
│   ├── __init__.py
│   ├── constants.py       # Vella's System Prompt & Persona Rules
│   └── agent.py           # Long-form streaming logic
│
└── volco/                 # 🗣️ VOLCO'S LOGIC (Hardware/Voice)
    ├── __init__.py
    ├── agent.py           # Short-form, fast streaming logic
    └── router.py          # WebSocket logic & audio buffer handling

```

---

## 🔌 API Endpoints

### **Authentication**

* `POST /auth/register` — Create a new user account.
* `POST /auth/login` — Authenticate and retrieve User ID.

### **Vella (Chat & History)**

* `POST /chat` — Stream LLM responses (Saves to DB automatically).
* `GET /history/sessions?user_id={id}` — Retrieve list of past conversations.
* `GET /history/{session_id}` — Retrieve full message history for a chat.

### **Voice Features (REST)**

* `POST /stt` — Transcribe audio file to text (Whisper).
* `POST /tts` — Synthesize text to audio file (Piper).

### **Volco (Real-Time Voice)**

* `WS /volco_ws` — WebSocket endpoint for continuous audio streaming, transcription, and instant TTS playback. Supports `device` and `app` client types.

---

## 🛣️ Roadmap

* [x] **PostgreSQL Integration:** Full persistence for chats and users.
* [x] **Modular Architecture:** Split logic into `vella`, `volco`, and `shared` to optimize VRAM.
* [x] **Real-Time Audio Streaming:** WebSockets implemented for zero-latency voice interaction.
* [x] **Action Engine:** Hardware-level command execution.
* [ ] **Weaviate Integration:** Fully connect semantic search to the LLM context window.
* [ ] **Secure Auth:** Upgrade simple ID auth to JWT (JSON Web Tokens).

---

**Developed by Void Tech.** *Private, Local, Intelligent.*