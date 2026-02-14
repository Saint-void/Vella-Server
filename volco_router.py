import os
import re
import subprocess
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

# ✅ FIX: Match the signature exactly to satisfy Pylance
try:
    from chat_agent import stream_generate
except ImportError:
    print("⚠️ Warning: chat_agent.py not found. LLM will fail.")
    # The backup function must use 'prompt' just like the real one
    def stream_generate(prompt: str, max_new_tokens: int = 128): 
        yield "Error: Agent missing."

# ✅ Initialize Global Variables
vosk_model = None
KaldiRecognizer = None

try:
    from vosk import Model, KaldiRecognizer as VoskRec
    KaldiRecognizer = VoskRec
except ImportError:
    print("❌ Vosk Library not installed. Run: pip install vosk")

# =============================
# CONFIGURATION
# =============================
# ⚠️ CHECK YOUR PATHS
PIPER_EXE = r"V:/Document/Vella-Modes/models/piper/piper.exe"
VOICE_MODEL = r"V:/Document/Vella-Modes/models/tts-piper/en_US-lessac-medium.onnx"
VOSK_MODEL_PATH = r"V:/Document/Vella-Modes/models/vosk/vosk-model-en-us-0.22"

router = APIRouter()

# =============================
# INITIALIZE VOSK ENGINE
# =============================
print(f"🎧 Loading Vosk from: {VOSK_MODEL_PATH}")

if os.path.exists(VOSK_MODEL_PATH):
    try:
        # Only load if the library was imported successfully
        if 'Model' in locals() and Model:
            vosk_model = Model(VOSK_MODEL_PATH)
            print("✅ Vosk Loaded Successfully")
    except Exception as e:
        print(f"❌ Vosk Load Error: {e}")
else:
    print(f"❌ Model not found at: {VOSK_MODEL_PATH}")

# =============================
# HELPERS
# =============================
def generate_piper_pcm(text: str) -> bytes:
    if not text.strip(): return b""
    
    if not os.path.exists(PIPER_EXE):
        return b""

    command = [PIPER_EXE, "--model", VOICE_MODEL, "--output-raw"]
    try:
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout_data, _ = process.communicate(input=text.encode('utf-8'))
        return stdout_data
    except:
        return b""

async def stream_audio_response_ws(prompt: str, websocket: WebSocket):
    buffer = ""
    sentence_endings = re.compile(r'(?<=[.!?])\s+')
    
    print(f"🧠 Volco Thinking...")
    try:
        # Loop through tokens from the LLM
        for token in stream_generate(prompt):
            buffer += token
            parts = sentence_endings.split(buffer)
            
            # If we find a full sentence, speak it immediately
            if len(parts) > 1:
                sentence = parts[0]
                buffer = parts[1]
                if sentence.strip():
                    pcm = generate_piper_pcm(sentence)
                    if pcm: 
                        await websocket.send_bytes(pcm)
                    await asyncio.sleep(0.01) # Tiny pause for stability

        # Speak any remaining text
        if buffer.strip():
            pcm = generate_piper_pcm(buffer)
            if pcm: await websocket.send_bytes(pcm)
                
    except Exception as e:
        print(f"❌ LLM Stream Error: {e}")
        try:
            await websocket.send_text("NO_SPEECH")
        except:
            pass

# =============================
# WEBSOCKET ENDPOINT
# =============================
@router.websocket("/volco_ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    if not vosk_model or not KaldiRecognizer:
        print("❌ Server Error: Vosk Model not loaded.")
        await websocket.close()
        return

    print("🔌 Volco Connected")
    
    # Create recognizer for this specific connection
    rec = KaldiRecognizer(vosk_model, 16000)
    
    try:
        while True:
            data = await websocket.receive()
            
            if "bytes" in data:
                # Process audio chunk
                if rec.AcceptWaveform(data["bytes"]):
                    pass

            elif "text" in data and data["text"] == "COMMIT":
                # User finished speaking
                result_json = rec.FinalResult()
                final_text = json.loads(result_json).get("text", "").strip()
                
                print(f"🗣️ User Said: '{final_text}'")
                
                if final_text:
                    await stream_audio_response_ws(final_text, websocket)
                    await websocket.send_text("END_OF_RESPONSE")
                else:
                    await websocket.send_text("NO_SPEECH")
                
                rec.Reset()

    except WebSocketDisconnect:
        print("🔌 Volco Disconnected")
    except Exception as e:
        print(f"❌ Critical WebSocket Error: {e}")