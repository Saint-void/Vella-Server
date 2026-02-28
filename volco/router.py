import os
import re
import wave
import asyncio
import tempfile
import subprocess
from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from starlette.concurrency import iterate_in_threadpool
import asyncio

# ⚡ IMPORT ALREADY LOADED WHISPER FROM SHARED
from shared.models import whisper_model

# Import Volco-specific modules
from volco.connection import volco_manager
from volco.action_engine import ActionEngine
from volco.agent import stream_generate

action_engine = ActionEngine()
router = APIRouter()

# ==========================================
# ⚙️ CONFIGURATION & PATHS
# ==========================================
PIPER_EXE = r"V:/Document/Vella-Modes/models/piper/piper.exe"
VOICE_MODEL = r"V:/Document/Vella-Modes/models/tts-piper/en_US-lessac-medium.onnx"

# ==========================================
# 🗣️ TEXT TO SPEECH (Piper)
# ==========================================
def generate_piper_pcm(text: str) -> bytes:
    if not text.strip() or not os.path.exists(PIPER_EXE): return b""
    command = [PIPER_EXE, "--model", VOICE_MODEL, "--output-raw"]
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout_data, _ = process.communicate(input=text.encode('utf-8'))
        return stdout_data
    except: return b""

# ==========================================
# 🔄 STREAMING LOGIC
# ==========================================
async def speak_simple_message(text: str, websocket: WebSocket, user_id: str):
    """Speaks a single, pre-calculated message (for commands)."""
    await volco_manager.broadcast_to_app(user_id, {"role": "ai_start", "content": ""})
    await volco_manager.broadcast_to_app(user_id, {"role": "ai_token", "content": text})
    
    # ⚡ NEW: Offload Piper TTS generation to a background thread
    pcm = await asyncio.to_thread(generate_piper_pcm, text)
    
    if pcm: await websocket.send_bytes(pcm)
    await volco_manager.broadcast_to_app(user_id, {"role": "ai_end", "content": ""})

async def stream_audio_response_ws(prompt: str, websocket: WebSocket, user_id: str) -> bool:
    """Streams LLM generation out to audio chunks and prints to terminal."""
    buffer = ""
    sentence_endings = re.compile(r'(?<=[.!?¡¿,;])\s+')
    try:
        await volco_manager.broadcast_to_app(user_id, {"role": "ai_start", "content": ""})
        print(f"🤖 Volco: ", end="", flush=True)
        
        # ⚡ NEW: Iterate the LLM in a threadpool so it doesn't freeze the websocket!
        async for token in iterate_in_threadpool(stream_generate(prompt)):
            buffer += token
            print(token, end="", flush=True)
            
            await volco_manager.broadcast_to_app(user_id, {"role": "ai_token", "content": token})
            parts = sentence_endings.split(buffer)
            if len(parts) > 1:
                sentence = parts[0]; buffer = parts[1]
                if sentence.strip():
                    # ⚡ NEW: Offload Piper TTS generation to a background thread
                    pcm = await asyncio.to_thread(generate_piper_pcm, sentence)
                    if pcm: await websocket.send_bytes(pcm)
                    
        if buffer.strip():
            pcm = await asyncio.to_thread(generate_piper_pcm, buffer)
            if pcm: await websocket.send_bytes(pcm)
            
        print()
        await volco_manager.broadcast_to_app(user_id, {"role": "ai_end", "content": ""})
        return True 
    except Exception as e: 
        # Added 'repr' so if it crashes again, we see the exact error type!
        print(f"\n❌ Stream Error: {repr(e)}") 
        return False

# ==========================================
# 🔌 WEBSOCKET ENDPOINT
# ==========================================
@router.websocket("/volco_ws")
async def websocket_endpoint(websocket: WebSocket, client_type: str = Query(...), user_id: str = Query(...)):
    await volco_manager.connect(user_id, client_type, websocket)
    audio_buffer = bytearray()

    try:
        if client_type == "app":
            while True: await websocket.receive_text()

        elif client_type == "device":
            if not whisper_model: 
                print("❌ No Whisper model loaded in shared.models. Closing socket.")
                await websocket.close()
                return
            
            while True:
                data = await websocket.receive()
                if "text" in data and data["text"] == "PING": continue 

                if "bytes" in data:
                    audio_buffer.extend(data["bytes"])

                # ⚡ ADD THIS: Clear the buffer if the client says the audio was junk
                elif "text" in data and data["text"] == "CLEAR":
                    audio_buffer = bytearray()
                    print(f"🗑️ {user_id}: Client ignored noise, buffer cleared.")

                elif "text" in data and data["text"] == "COMMIT":
                    text = ""
                    # ... (the rest of the transcription logic stays the same)
                    if len(audio_buffer) > 0:
                        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as temp_wav:
                            temp_filename = temp_wav.name
                            with wave.open(temp_filename, "wb") as wf:
                                wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000)
                                wf.writeframes(audio_buffer)
                                
                        try:
                            # ⚡ Using the global whisper_model
                            segments, _ = whisper_model.transcribe(temp_filename, beam_size=1, language="en", condition_on_previous_text=False)
                            text = " ".join([s.text for s in segments]).strip()
                        except Exception as e: print(f"Transcribe Error: {e}")
                        
                        try: os.remove(temp_filename)
                        except: pass
                        audio_buffer = bytearray() 

                    print(f"🗣️ {user_id}: {text}")

                    if text:
                        await volco_manager.broadcast_to_app(user_id, {"role": "user", "content": text})

                        # 1. Check for Action Commands
                        is_command, response_text = action_engine.execute(text)

                        if is_command:
                            print(f"🤖 Action Executed: {response_text}")
                            await speak_simple_message(response_text, websocket, user_id)
                        else:
                            # 2. Fallback to LLM Chat
                            success = await stream_audio_response_ws(text, websocket, user_id)
                            if not success: break 

                        await websocket.send_text("END_OF_RESPONSE")
                    else:
                        await websocket.send_text("NO_SPEECH")

    except WebSocketDisconnect: volco_manager.disconnect(user_id, client_type)
    except RuntimeError: volco_manager.disconnect(user_id, client_type)
    except Exception as e: print(f"Error: {e}"); volco_manager.disconnect(user_id, client_type)