Here is the updated **README.md** for the **Vella Server (Backend)**.

I have updated it to **v4.0.0** to reflect the major database integration, added the PostgreSQL setup instructions, and updated the project structure to include the new `db.py` and `auth.py` files.

---

# 🧠 Vella AI Server (Backend)

> **Local Intelligence Engine for Vella Chat.**
> *v4.0.0 | FastAPI | PostgreSQL | Piper TTS | Faster-Whisper*

The Vella Server is the local backend that powers the Vella Chat Interface. It handles LLM inference, voice processing (STT/TTS), and now features **Persistent Long-Term Memory** via PostgreSQL.

**New in v4.0.0:** Complete PostgreSQL integration for user authentication and chat history persistence.

---

## 🛠️ Core Technology Stack

* **API Framework:** `FastAPI` (Python 3.10+) running on `Uvicorn`.
* **Database:** `PostgreSQL` — *Stores Users, Sessions, and Message Logs.*
* **LLM Engine:** Custom `chat_agent.py` using `TextIteratorStreamer` for real-time token generation.
* **Voice Engine:**
* **STT:** `Faster-Whisper` (Local, CPU/GPU optimized).
* **TTS:** `Piper TTS` (Zero-latency local synthesis).


* **Memory:** `Weaviate` — Vector database for semantic context retrieval.
* **Tunneling:** `ngrok` — Securely exposes localhost to the Android frontend.

---

## 🚀 Quick Start Guide

### 1. Prerequisites

* **Python 3.10+**
* **PostgreSQL** installed and running locally.
* **FFmpeg** installed and added to system PATH.

### 2. Database Configuration

Create a `.env` file in the `backend/` directory or ensure your `db.py` defaults match your local Postgres setup:

```env
# Example .env configuration
DATABASE_URL="postgresql://postgres:password@localhost:5432/vella"

```

*Note: The server will automatically create the necessary tables (`users`, `sessions`, `messages`) on the first run.*

### 3. Installation

```bash
cd backend

# Create Virtual Environment (Optional but recommended)
python -m venv venv
# Windows: venv\Scripts\activate
# Mac/Linux: source venv/bin/activate

# Install Dependencies
pip install fastapi uvicorn psycopg2-binary python-dotenv transformers torch faster-whisper

```

### 4. Start the Server

Run the server using Uvicorn on **Port 8001**:

```bash
# Run with auto-reload for development
uvicorn main:app --reload --host 0.0.0.0 --port 8001

```

### 5. Open the Tunnel

To allow the Android app to connect:

```bash
ngrok http 8001

```

---

## 📂 Project Structure

```text
VELLA-SERVER/
├── main.py             # Entry point (FastAPI App, Routes, & Startup Logic)
├── db.py               # Database Connection & Schema Initialization (Postgres)
├── auth.py             # User Authentication (Register/Login Endpoints)
├── chat_agent.py       # LLM Logic & Streaming Generator
├── vector_store.py     # Weaviate Connection for Semantic Memory
├── requirements.txt    # Python Dependencies
└── .env                # (Optional) Environment Variables

```

---

## 🔌 API Endpoints

### **Authentication**

* `POST /auth/register` — Create a new user account.
* `POST /auth/login` — Authenticate and retrieve User ID.

### **Chat & History**

* `POST /chat` — Stream LLM responses (Saves to DB automatically).
* `GET /history/sessions?user_id={id}` — Retrieve list of past conversations.
* `GET /history/{session_id}` — Retrieve full message history for a chat.

### **Voice Features**

* `POST /stt` — Transcribe audio file to text (Whisper).
* `POST /tts` — Synthesize text to audio file (Piper).

---

## 🛣️ Roadmap

* [x] **PostgreSQL Integration:** Full persistence for chats and users.
* [x] **Real-Time Streaming:** Text-to-speech pipeline and token streaming.
* [ ] **Secure Auth:** Upgrade simple ID auth to JWT (JSON Web Tokens).
* [ ] **Long-Term Memory:** Connect Weaviate to recall specific user facts.
* [ ] **File Analysis:** Add endpoint to parse PDFs and text files.

---

**Developed by Vella AI Systems.** *Private, Local, Intelligent.*