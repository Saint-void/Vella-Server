# Volco — Real-Time Voice Assistant Backend

Volco is a low-latency, WebRTC-powered voice assistant that runs on a connected headset. It handles end-to-end voice interaction: STT via Whisper, intent classification, Spotify control, LLM-powered conversation, and TTS via Kokoro — all over a **single persistent WebRTC data channel**.

---

## Architecture

```
Headset Mic
    ↓  raw 16kHz PCM bytes  (WebRTC data channel)
ASR — MLX Whisper tiny.en  (Apple Silicon GPU/Neural Engine)
    ↓  transcribed text
Intent Classifier — qwen2.5:1.5b  (Ollama, local)
    ↓  intent + action
Intent Router
    ├── Spotify intent  →  JSON command  ──────────────────────────→  WebRTC  →  Headset
    └── Conversation    →  Ollama LLM   →  Kokoro TTS (WAV bytes)  →  WebRTC  →  Headset Speaker
```

---

## WebRTC Data Channel Protocol

Volco uses a **single WebRTC data channel** for all communication between the headset and the server. Messages are either binary (audio) or UTF-8 strings (commands / JSON).

### Device → Server (Upstream)

| Message     | Type     | Description                                          |
|-------------|----------|------------------------------------------------------|
| Audio data  | `bytes`  | Raw 16kHz 16-bit mono PCM streamed from the mic      |
| `COMMIT`    | `string` | Trigger ASR transcription on the buffered audio      |
| `CLEAR`     | `string` | Discard the current audio buffer                     |
| `PING`      | `string` | Keepalive heartbeat                                  |

### Server → Device (Downstream)

| Message          | Type            | Description                                                              |
|------------------|-----------------|--------------------------------------------------------------------------|
| TTS audio        | `bytes`         | Complete WAV file (RIFF header, 24 kHz, 16-bit mono PCM)                |
| Spotify command  | `string` (JSON) | `{"action": "spotify_play_track", "query": "Hope by NF", ...}`          |
| Session control  | `string` (JSON) | `{"action": "none", "continue_session": bool, "end_session": bool}`      |
| `NO_SPEECH`      | `string`        | ASR returned no transcription for the committed audio                    |
| `END_OF_RESPONSE`| `string`        | The full assistant response (audio + commands) is complete               |

---

## TTS Audio Protocol

TTS is synthesized by **Kokoro ONNX** and delivered as **complete WAV files** over the binary data channel. Each binary message the device receives is one self-contained WAV file — no reassembly required.

### Detecting a WAV message

Every WAV file starts with the 4-byte ASCII magic bytes `RIFF`. Check the first 4 bytes of any incoming binary message:

```
message[0:4] == b"RIFF"  →  this is a complete WAV file, play it
```

### Reading the total WAV size from the header

```
total_bytes = uint32_little_endian(message[4:8]) + 8
```

The full WAV header layout:

```
Bytes 0–3:   "RIFF"            (magic)
Bytes 4–7:   file_size - 8     (uint32, little-endian)
Bytes 8–11:  "WAVE"            (format)
Bytes 12+:   fmt + data chunks (standard PCM)
```

### Playback behaviour

| Response type          | WAV messages sent                                            |
|------------------------|--------------------------------------------------------------|
| Short intent response  | One WAV for the entire message                               |
| LLM conversation       | One WAV per sentence, sent sequentially as tokens arrive     |

For conversational responses, queue each incoming WAV and play them back-to-back. This gives low latency (first audio arrives quickly) with clean, crackle-free playback (each WAV is a complete, properly formed file).

---

## Voice Session Flow

```
1.  Headset detects wake word        →  starts streaming raw PCM bytes upstream
2.  Headset detects end of speech    →  sends "COMMIT"
3.  Server runs ASR                  →  text transcription
4.  Server classifies intent         →  routes to action handler
5a. Spotify intent                   →  server sends JSON command + WAV confirmation
5b. Conversation intent              →  server streams LLM tokens
                                         sends one WAV per completed sentence
6.  Server sends "END_OF_RESPONSE"
7.  Headset reads continue_session / end_session to decide next state
```

---

## Supported Intents

| Intent                  | Example Trigger                        |
|-------------------------|----------------------------------------|
| `spotify_play`          | "Play Hope by NF"                      |
| `spotify_play_playlist` | "Play my chill playlist"               |
| `spotify_play_album`    | "Play the Fear album"                  |
| `spotify_next`          | "Next song" / "Skip"                   |
| `spotify_previous`      | "Previous track" / "Go back"           |
| `spotify_resume`        | "Resume" / "Continue" / "Play music"   |
| `spotify_pause`         | "Pause" / "Stop the music"             |
| `conversation`          | Anything else → LLM fallback           |

---

## Models

| Component            | Model                                   | Notes                                       |
|----------------------|-----------------------------------------|---------------------------------------------|
| STT (Volco)          | `mlx-community/whisper-tiny.en-mlx`     | Apple Silicon GPU, optimised for low latency|
| STT (Vella)          | `mlx-community/whisper-medium.en-mlx`   | Higher accuracy for web chat                |
| Intent Classifier    | `qwen2.5:1.5b` via Ollama              | Fast, runs locally                          |
| Conversation LLM     | `qwen2.5:3b` via Ollama                | Chat fallback                               |
| TTS                  | Kokoro ONNX — `af_heart` voice          | 24 kHz, 16-bit mono WAV output              |

---

## Environment Variables

| Variable                   | Default                                  | Description                          |
|----------------------------|------------------------------------------|--------------------------------------|
| `VOLCO_WHISPER_MLX_REPO`   | `mlx-community/whisper-tiny.en-mlx`      | Whisper model for Volco STT          |
| `WHISPER_MLX_REPO`         | `mlx-community/whisper-medium.en-mlx`    | Whisper model for Vella STT          |
| `OLLAMA_BASE_URL`          | `http://localhost:11434`                 | Ollama server base URL               |
| `OLLAMA_VOLCO_DEFAULT_MODEL`| `qwen2.5:1.5b`                          | LLM used for agent generation        |
| `DATABASE_URL`             | —                                        | PostgreSQL connection string         |
| `KOKORO_VOICE`             | `af_heart`                               | Default Kokoro TTS voice             |
| `KOKORO_SPEED`             | `1.2`                                    | Default TTS speed multiplier         |
| `KOKORO_LANG`              | `en-us`                                  | Default TTS language                 |

---

## Setup

Install dependencies:

```bash
pip install mlx-whisper kokoro-onnx soundfile fastapi aiortc psycopg2-binary python-dotenv
```

Pull Ollama models:

```bash
ollama pull qwen2.5:1.5b
ollama pull qwen2.5:3b
```

Start the server:

```bash
uvicorn main:app --host 0.0.0.0 --port 8001
```

---

## Key Design Decisions

**Single WebRTC data channel for everything** — STT audio goes up as raw PCM bytes, TTS comes down as WAV bytes, Spotify commands come down as JSON strings. One connection handles the full duplex session.

**WAV over raw PCM for TTS** — Sending complete WAV files (with RIFF headers) instead of raw PCM chunks eliminates crackling caused by boundary discontinuities, pacing mismatches, and missing audio headers. The device receives one clean, self-contained file per sentence.

**Sentence-level TTS pipelining for conversation** — Rather than waiting for the full LLM response before synthesising speech, each completed sentence is synthesised and sent immediately. This keeps first-audio latency low while still producing crackle-free output.

**Apple Silicon MLX acceleration** — Both Whisper models use the MLX framework to run on the M-series GPU and Neural Engine, keeping STT latency well below 300 ms for short voice commands.