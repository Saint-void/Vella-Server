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

# 🆕 IMPORT THE ACTION ENGINE
from action_engine import ActionEngine 
action_engine = ActionEngine()

# --- IMPORTS ---
try:
    from chat_agent import stream_generate
except ImportError:
    # ⚡ CHANGED: Added is_voice=False to match the new signature
    def stream_generate(prompt: str, max_new_tokens: int = 128, is_voice: bool = False): 
        yield f"Echo: {prompt}"

# ⚙️ CONFIGURATION
PIPER_EXE = r"V:/Document/Vella-Modes/models/piper/piper.exe"
VOICE_MODEL = r"V:/Document/Vella-Modes/models/tts-piper/en_US-lessac-medium.onnx"
MODEL_PRIMARY_PATH = r"V:/Document/Vella-Modes/models/models--distil-whisper--distil-large-v3/snapshots/latest"
MODEL_FALLBACK_PATH = r"V:/Document/Vella-Modes/models/models--Systran--faster-whisper-small/snapshots/536b0662742c02347bc0e980a01041f333bce120"

router = APIRouter()

# 🧠 MODEL LOADING 
whisper_model = None
print(f"\n🎧 Initializing Whisper AI...")
try:
    print(f"   👉 Attempting to load Primary: Distil-Large-V3...")
    whisper_model = WhisperModel(MODEL_PRIMARY_PATH, device="cuda", compute_type="float16")
    print("   ✅ SUCCESS: Primary Model Loaded (GPU/Float16)!")
except Exception as e_primary:
    print(f"   ⚠️ Primary Load Failed: {e_primary}")
    try:
        print(f"   👉 Attempting to load Fallback: Faster-Whisper-Small...")
        whisper_model = WhisperModel(MODEL_FALLBACK_PATH, device="cpu", compute_type="int8")
        print("   ✅ SUCCESS: Fallback Model Loaded (CPU/Int8)!")
    except Exception:
        whisper_model = None

# 📡 CONNECTION MANAGER
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, Dict[str, WebSocket]] = {}
    async def connect(self, user_id: str, client_type: str, websocket: WebSocket):
        await websocket.accept()
        if user_id not in self.active_connections: self.active_connections[user_id] = {}
        self.active_connections[user_id][client_type] = websocket
        print(f"🔌 {user_id} ({client_type}) Connected")
    def disconnect(self, user_id: str, client_type: str):
        if user_id in self.active_connections:
            if client_type in self.active_connections[user_id]: del self.active_connections[user_id][client_type]
            if not self.active_connections[user_id]: del self.active_connections[user_id]
        print(f"🔌 {user_id} ({client_type}) Disconnected")
    async def broadcast_to_app(self, user_id: str, message: dict):
        if user_id in self.active_connections and "app" in self.active_connections[user_id]:
            try: await self.active_connections[user_id]["app"].send_json(message)
            except: pass
manager = ConnectionManager()

# --- AUDIO GENERATION ---
def generate_piper_pcm(text: str) -> bytes:
    if not text.strip() or not os.path.exists(PIPER_EXE): return b""
    command = [PIPER_EXE, "--model", VOICE_MODEL, "--output-raw"]
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout_data, _ = process.communicate(input=text.encode('utf-8'))
        return stdout_data
    except: return b""

# --- STREAMING LOGIC ---
async def stream_audio_response_ws(prompt: str, websocket: WebSocket, user_id: str) -> bool:
    buffer = ""
    sentence_endings = re.compile(r'(?<=[.!?¡¿,;])\s+')
    try:
        await manager.broadcast_to_app(user_id, {"role": "ai_start", "content": ""})
        
        # ⚡ CHANGED: Passed is_voice=True to the generator
        for token in stream_generate(prompt, is_voice=True):
            buffer += token
            await manager.broadcast_to_app(user_id, {"role": "ai_token", "content": token})
            parts = sentence_endings.split(buffer)
            if len(parts) > 1:
                sentence = parts[0]; buffer = parts[1]
                if sentence.strip():
                    pcm = generate_piper_pcm(sentence)
                    if pcm: await websocket.send_bytes(pcm)
                    await asyncio.sleep(0.01)
        if buffer.strip():
            pcm = generate_piper_pcm(buffer)
            if pcm: await websocket.send_bytes(pcm)
        await manager.broadcast_to_app(user_id, {"role": "ai_end", "content": ""})
        return True 
    except: return False

# ⚡ NEW: SIMPLE AUDIO RESPONDER
async def speak_simple_message(text: str, websocket: WebSocket, user_id: str):
    await manager.broadcast_to_app(user_id, {"role": "ai_start", "content": ""})
    await manager.broadcast_to_app(user_id, {"role": "ai_token", "content": text})
    pcm = generate_piper_pcm(text)
    if pcm: await websocket.send_bytes(pcm)
    await manager.broadcast_to_app(user_id, {"role": "ai_end", "content": ""})

# ==========================================
# 🔌 WEBSOCKET ENDPOINT
# ==========================================
@router.websocket("/volco_ws")
async def websocket_endpoint(websocket: WebSocket, client_type: str = Query(...), user_id: str = Query(...)):
    await manager.connect(user_id, client_type, websocket)
    audio_buffer = bytearray()

    try:
        if client_type == "app":
            while True: await websocket.receive_text()

        elif client_type == "device":
            if not whisper_model: 
                print("❌ No Whisper model loaded."); await websocket.close(); return
            
            while True:
                data = await websocket.receive()
                if "text" in data and data["text"] == "PING": continue 

                if "bytes" in data:
                    audio_buffer.extend(data["bytes"])

                elif "text" in data and data["text"] == "COMMIT":
                    text = ""
                    if len(audio_buffer) > 0:
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
                            temp_filename = temp_wav.name
                            with wave.open(temp_filename, "wb") as wf:
                                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
                                wf.writeframes(audio_buffer)
                        try:
                            segments, _ = whisper_model.transcribe(temp_filename, beam_size=1, language="en", condition_on_previous_text=False)
                            text = " ".join([s.text for s in segments]).strip()
                        except Exception as e: print(f"Transcribe Error: {e}")
                        try: os.remove(temp_filename)
                        except: pass
                        audio_buffer = bytearray() 

                    print(f"🗣️ {user_id}: {text}")

                    if text:
                        await manager.broadcast_to_app(user_id, {"role": "user", "content": text})

                        # ⚡ 1. CHECK FOR COMMANDS FIRST
                        is_command, response_text = action_engine.execute(text)

                        if is_command:
                            print(f"🤖 Action Executed: {response_text}")
                            await speak_simple_message(response_text, websocket, user_id)
                        else:
                            # ⚡ 2. IF NOT A COMMAND, SEND TO LLM
                            success = await stream_audio_response_ws(text, websocket, user_id)
                            if not success: break 

                        await websocket.send_text("END_OF_RESPONSE")
                    else:
                        await websocket.send_text("NO_SPEECH")

    except WebSocketDisconnect: manager.disconnect(user_id, client_type)
    except RuntimeError: manager.disconnect(user_id, client_type)
    except Exception as e: print(f"Error: {e}"); manager.disconnect(user_id, client_type)