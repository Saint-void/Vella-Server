import os
import re
import subprocess
import asyncio
import json
import wave
import tempfile
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from typing import Dict
from faster_whisper import WhisperModel

# --- IMPORTS ---
try:
    from chat_agent import stream_generate
except ImportError:
    def stream_generate(prompt: str, max_new_tokens: int = 128): 
        yield f"Echo: {prompt}"

# ⚠️ CHECK PATHS
PIPER_EXE = r"V:/Document/Vella-Modes/models/piper/piper.exe"
VOICE_MODEL = r"V:/Document/Vella-Modes/models/tts-piper/en_US-lessac-medium.onnx"
WHISPER_MODEL_PATH = r"V:/Document/Vella-Modes/models/models--Systran--faster-whisper-small/snapshots/536b0662742c02347bc0e980a01041f333bce120"

router = APIRouter()

# --- LOAD WHISPER ---
print(f"🎧 Loading Faster-Whisper...")
try:
    whisper_model = WhisperModel(
        WHISPER_MODEL_PATH,
        device="cpu",      # Change to "cuda" if you have a GPU
        compute_type="int8"
    )
    print("✅ Whisper Loaded!")
except Exception as e:
    print(f"❌ Whisper Load Error: {e}")
    whisper_model = None

# --- CONNECTION MANAGER ---
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}

    async def connect(self, user_id: str, client_type: str, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections:
            self.active_connections[user_id] = {}
        self.active_connections[user_id][client_type] = websocket
        print(f"🔌 {user_id} ({client_type}) Connected")

    def disconnect(self, user_id: str, client_type: str):
        if user_id in self.active_connections:
            if client_type in self.active_connections[user_id]:
                del self.active_connections[user_id][client_type]
            if not self.active_connections[user_id]:
                del self.active_connections[user_id]
        print(f"🔌 {user_id} ({client_type}) Disconnected")

    async def broadcast_to_app(self, user_id: str, message: dict):
        if user_id in self.active_connections and "app" in self.active_connections[user_id]:
            try:
                await self.active_connections[user_id]["app"].send_json(message)
            except: pass

manager = ConnectionManager()

# --- HELPER: AUDIO GENERATION ---
def generate_piper_pcm(text: str) -> bytes:
    if not text.strip() or not os.path.exists(PIPER_EXE): return b""
    command = [PIPER_EXE, "--model", VOICE_MODEL, "--output-raw"]
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout_data, _ = process.communicate(input=text.encode('utf-8'))
        return stdout_data
    except: return b""

# --- HELPER: STREAMING ---
async def stream_audio_response_ws(prompt: str, websocket: WebSocket, user_id: str) -> bool:
    buffer = ""
    sentence_endings = re.compile(r'(?<=[.!?¡¿,;])\s+')
    
    try:
        await manager.broadcast_to_app(user_id, {"role": "ai_start", "content": ""})

        for token in stream_generate(prompt):
            buffer += token
            await manager.broadcast_to_app(user_id, {"role": "ai_token", "content": token})

            parts = sentence_endings.split(buffer)
            if len(parts) > 1:
                sentence = parts[0]
                buffer = parts[1]
                if sentence.strip():
                    pcm = generate_piper_pcm(sentence)
                    if pcm: await websocket.send_bytes(pcm)
                    await asyncio.sleep(0.01)

        if buffer.strip():
            pcm = generate_piper_pcm(buffer)
            if pcm: await websocket.send_bytes(pcm)
        
        await manager.broadcast_to_app(user_id, {"role": "ai_end", "content": ""})
        return True 

    except Exception:
        return False

# ==========================================
# 🔌 WEBSOCKET ENDPOINT
# ==========================================
@router.websocket("/volco_ws")
async def websocket_endpoint(
    websocket: WebSocket, 
    client_type: str = Query(...), 
    user_id: str = Query(...)      
):
    await manager.connect(user_id, client_type, websocket)

    # 🎤 AUDIO BUFFER FOR WHISPER
    audio_buffer = bytearray()

    try:
        # --- APP ---
        if client_type == "app":
            while True: await websocket.receive_text()

        # --- DEVICE ---
        elif client_type == "device":
            if not whisper_model: 
                print("❌ Whisper model missing.")
                return
            
            while True:
                data = await websocket.receive()
                
                # Ignore Heartbeat
                if "text" in data and data["text"] == "PING":
                    continue 

                # 1. Collect Audio Bytes
                if "bytes" in data:
                    audio_buffer.extend(data["bytes"])

                # 2. Transcribe on COMMIT
                elif "text" in data and data["text"] == "COMMIT":
                    text = ""
                    
                    if len(audio_buffer) > 0:
                        # Save buffer to temp file for Whisper
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
                            temp_filename = temp_wav.name
                            with wave.open(temp_filename, "wb") as wf:
                                wf.setnchannels(1)
                                wf.setsampwidth(2) # 16-bit PCM
                                wf.setframerate(16000)
                                wf.writeframes(audio_buffer)
                        
                        # Transcribe
                        try:
                            segments, _ = whisper_model.transcribe(temp_filename, beam_size=5)
                            text = " ".join([s.text for s in segments]).strip()
                        except Exception as e:
                            print(f"Transcribe Error: {e}")
                        
                        # Cleanup
                        os.remove(temp_filename)
                        audio_buffer = bytearray() # Clear buffer

                    print(f"🗣️ {user_id}: {text}")

                    if text:
                        await manager.broadcast_to_app(user_id, {"role": "user", "content": text})
                        
                        success = await stream_audio_response_ws(text, websocket, user_id)
                        if not success: break 

                        await websocket.send_text("END_OF_RESPONSE")
                    else:
                        await websocket.send_text("NO_SPEECH")

    except WebSocketDisconnect:
        manager.disconnect(user_id, client_type)
    except RuntimeError:
        manager.disconnect(user_id, client_type)
    except Exception as e:
        print(f"Error: {e}")
        manager.disconnect(user_id, client_type)