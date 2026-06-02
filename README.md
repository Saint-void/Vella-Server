
---

# 🧠 Vella & Volco AI Server (Backend)

> **Local Intelligence Engine for Vella Chat & Volco Voice.**
> *v7.2.0 | FastAPI | PostgreSQL | Kokoro ONNX TTS | Piper TTS Fallback | Llama-CPP (GGUF) | WebRTC*

The Vella Server is the local backend that powers both the Vella Web Interface and the Volco Hardware/Voice Assistant.

**New in v7.1.0:** 
- **Llama-CPP Integration:** Migrated from `transformers` to `llama-cpp-python` for native GGUF support.
- **Apple Silicon (MPS) Native:** Optimized to run the entire LLM graph on Metal performance shaders (`n_gpu_layers=-1`).
- **Conversational Streaming:** Uses the `create_chat_completion` API for robust, template-free interaction with Gemma 3.
- **Consolidated Model Loading:** Shared `Llama` instance for Vella and Volco.

**New in v7.2.0:**
- **Kokoro ONNX TTS:** Vella `/tts` now uses Kokoro when available for a more natural voice.
- **Piper Fallback:** Piper still loads as a fallback and remains available for existing Volco paths.
- **Configurable Voice:** Set `KOKORO_VOICE`, `KOKORO_SPEED`, and `KOKORO_LANG` in `.env`.

---

## 🛠️ Core Technology Stack

* **API Framework:** `FastAPI` (Python 3.10+) running on `Uvicorn`.
* **Database:** `PostgreSQL` & `Weaviate`.
* **LLM Engine:** `Gemma 3 4B (GGUF Q4_K_M)` running via `llama-cpp-python` with **Full MPS (Metal) Acceleration**.
* **Voice Engine:**
  * **STT:** `Faster-Whisper medium.en` (running on optimized CPU int8 for Mac).
  * **TTS:** `Kokoro ONNX` for Vella, with `Piper TTS` fallback.
* **Real-Time Comm:** `WebRTC` (aiortc).

---

## 🚀 Quick Start Guide (macOS)

### 1. Prerequisites

* **Python 3.10+**
* **PostgreSQL & Weaviate** installed and running.
* **FFmpeg** installed (`brew install ffmpeg`).
* **Kokoro ONNX model files:** Place in `../models/kokoro/`.
* **Piper macOS Binary:** Place in `../models/piper/piper` and `chmod +x` for fallback/Volco compatibility.

### 2. Installation

```bash
# Create Virtual Environment
python -m venv .venv
source .venv/bin/activate

# Install Dependencies
pip install fastapi uvicorn psycopg2-binary python-dotenv \
            llama-cpp-python faster-whisper weaviate-client \
            sentence-transformers aiortc numpy huggingface_hub \
            kokoro-onnx soundfile
```

### 3. Kokoro TTS Setup

Create the Kokoro model folder:

```bash
mkdir -p ../models/kokoro
```

Download the Kokoro ONNX model and voice bundle:

```bash
curl -L https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx \
  -o ../models/kokoro/kokoro-v1.0.onnx

curl -L https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin \
  -o ../models/kokoro/voices-v1.0.bin
```

Optional `.env` settings:

```env
KOKORO_VOICE=af_sarah
KOKORO_SPEED=1.0
KOKORO_LANG=en-us
```

`KOKORO_SPEED` is clamped between `0.5` and `2.0`.

### 4. Kokoro Voices

Recommended voices to try first:

```text
af_sarah
af_bella
af_nova
af_sky
am_echo
am_liam
bf_emma
bm_daniel
```

Installed voice bundle:

```text
af_alloy
af_aoede
af_bella
af_heart
af_jessica
af_kore
af_nicole
af_nova
af_river
af_sarah
af_sky
am_adam
am_echo
am_eric
am_fenrir
am_liam
am_michael
am_onyx
am_puck
am_santa
bf_alice
bf_emma
bf_isabella
bf_lily
bm_daniel
bm_fable
bm_george
bm_lewis
ef_dora
em_alex
em_santa
ff_siwis
hf_alpha
hf_beta
hm_omega
hm_psi
if_sara
im_nicola
jf_alpha
jf_gongitsune
jf_nezumi
jf_tebukuro
jm_kumo
pf_dora
pm_alex
pm_santa
zf_xiaobei
zf_xiaoni
zf_xiaoxiao
zf_xiaoyi
zm_yunjian
zm_yunxi
zm_yunxia
zm_yunyang
```

### 5. Start the Server

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

---

## 📂 Project Structure

```text
vella-modes/
├── Vella-Server/          # Backend Application (This Repository)
└── models/                # Shared Model Storage
    ├── gemma-3-4b-it-gguf/
    ├── models--Systran--faster-whisper-medium.en/
    ├── kokoro/
    │   ├── kokoro-v1.0.onnx
    │   └── voices-v1.0.bin
    └── piper/             # Piper fallback voice model and binary
```

---

**Developed by Void Tech.** *Private, Local, Intelligent.*
