import os
import re
import wave
import asyncio
import tempfile
import subprocess
import json  # ⚡ NEW: Needed to stringify Spotify commands
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.concurrency import iterate_in_threadpool
from aiortc import RTCPeerConnection, RTCSessionDescription

# ⚡ IMPORT ALREADY LOADED WHISPER FROM SHARED
from shared.models import whisper_model

# Import Volco-specific modules
from volco.connection import volco_manager
from volco.action_engine import ActionEngine
from volco.agent import stream_generate
from .db import authenticate_mobile_user  

action_engine = ActionEngine()
router = APIRouter()

# ⚡ THE FIX: Memory Locks to prevent Python from Garbage Collecting our connections
active_connections = set()
active_channels = set()
user_interrupt_flags = {}

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

# ⚡ THE FIX: THE PACED CHUNKER
async def send_pcm_in_chunks(channel, pcm_data, user_id):
    CHUNK_SIZE = 16384
    for i in range(0, len(pcm_data), CHUNK_SIZE):

        # 🛑 STOP IMMEDIATELY
        if user_interrupt_flags.get(user_id, False):
            print("🛑 [SERVER] Stopping PCM stream mid-playback.")
            break

        if channel.readyState == "open":
            channel.send(pcm_data[i:i+CHUNK_SIZE])
            await asyncio.sleep(0.02)

# ==========================================
# 🔄 STREAMING LOGIC
# ==========================================
async def speak_simple_message(text: str, channel, user_id: str):
    await volco_manager.broadcast_to_app(user_id, {"role": "ai_start", "content": ""})
    await volco_manager.broadcast_to_app(user_id, {"role": "ai_token", "content": text})
    
    pcm = await asyncio.to_thread(generate_piper_pcm, text)
    if pcm: 
        await send_pcm_in_chunks(channel, pcm, user_id) 
        
    await volco_manager.broadcast_to_app(user_id, {"role": "ai_end", "content": ""})

async def stream_audio_response_rtc(prompt: str, channel, user_id: str) -> bool:
    buffer = ""
    sentence_endings = re.compile(r'(?<=[.!?¡¿,;])\s+')
    
    # ⚡ Reset the flag before starting a new response
    user_interrupt_flags[user_id] = False 
    
    try:
        await volco_manager.broadcast_to_app(user_id, {"role": "ai_start", "content": ""})
        print(f"🤖 Volco: ", end="", flush=True)
        
        async for token in iterate_in_threadpool(stream_generate(prompt)):
            if user_interrupt_flags.get(user_id, False):
                print("\n🛑 [SERVER] AI Generation aborted mid-sentence.")
                stream_generate.close()  # ⚡ safely close the generator
                break
                
            buffer += token
            print(token, end="", flush=True)
            
            await volco_manager.broadcast_to_app(user_id, {"role": "ai_token", "content": token})
            parts = sentence_endings.split(buffer)
            if len(parts) > 1:
                sentence = parts[0]; buffer = parts[1]
                if sentence.strip():
                    # Process TTS for this sentence
                    pcm = await asyncio.to_thread(generate_piper_pcm, sentence)
                    if pcm: await send_pcm_in_chunks(channel, pcm, user_id)
                    
        # ⚡ Only process the final chunk if we weren't interrupted
        if buffer.strip() and not user_interrupt_flags.get(user_id, False):
            pcm = await asyncio.to_thread(generate_piper_pcm, buffer)
            if pcm: await send_pcm_in_chunks(channel, pcm, user_id)
            
        print()
        await volco_manager.broadcast_to_app(user_id, {"role": "ai_end", "content": ""})
        return True 
    except Exception as e: 
        print(f"\n❌ Stream Error: {repr(e)}") 
        return False

# ==========================================
# 🧠 THE AI BRAIN 
# ==========================================
async def process_voice_commit(audio_buffer: bytearray, channel, user_id: str):
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
        except Exception as e: 
            print(f"Transcribe Error: {e}")
        
        try: os.remove(temp_filename)
        except: pass

    print(f"🗣️ {user_id}: {text}")

    if text:
        await volco_manager.broadcast_to_app(user_id, {"role": "user", "content": text})
        
        # ⚡ THE FIX: Unpack 3 values (is_command, voice_text, and the payload)
        is_command, response_text, payload = action_engine.execute(text)

        if is_command:
            print(f"🤖 Action Executed: {response_text}")
            
            # ⚡ NEW: If the engine returned a Spotify command, send it to the Pi!
            if payload and channel.readyState == "open":
                channel.send(json.dumps(payload))
                print(f"📡 Sent JSON Command to Headset: {payload}")

            await speak_simple_message(response_text, channel, user_id)
        else:
            await stream_audio_response_rtc(text, channel, user_id)

        await asyncio.sleep(0.5)
        if channel.readyState == "open":
            channel.send("END_OF_RESPONSE")
    else:
        if channel.readyState == "open":
            channel.send("NO_SPEECH")

# ==========================================
# 🔌 WEBRTC SIGNALING ENDPOINT
# ==========================================
@router.post("/volco_webrtc/offer")
async def webrtc_offer(request: Request):
    params = await request.json()
    user_id = params.get("user_id", "sogolo")
    
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])
    pc = RTCPeerConnection()
    active_connections.add(pc)

    @pc.on("datachannel")
    def on_datachannel(channel):
        active_channels.add(channel) 
        
        print(f"⚡ [WEBRTC] UDP Channel '{channel.label}' opened for {user_id}")
        audio_buffer = bytearray()

        @channel.on("message")
        def on_message(message):
            nonlocal audio_buffer
            if isinstance(message, bytes):
                audio_buffer.extend(message)
            elif isinstance(message, str):
                if message == "PING": pass 
                elif message == "CLEAR":
                    audio_buffer = bytearray()
                elif message == "COMMIT":
                    asyncio.create_task(process_voice_commit(bytearray(audio_buffer), channel, user_id))
                    audio_buffer = bytearray()
                # ⚡ NEW: CATCH THE KILL SIGNAL
                elif message == "INTERRUPT":
                    print(f"\n🛑 [SERVER] Interrupt received! Killing LLM & TTS for {user_id}...")
                    user_interrupt_flags[user_id] = True

                    # 🔥 Force flush behavior
                    asyncio.create_task(
                        volco_manager.broadcast_to_app(user_id, {"role": "ai_end", "content": ""})
                    )

    @pc.on("connectionstatechange") 
    async def on_connectionstatechange():
        print(f"📶 [WEBRTC] Connection state: {pc.connectionState}")
        if pc.connectionState in ["failed", "closed"]:
            active_connections.discard(pc)

    await pc.setRemoteDescription(offer)
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return JSONResponse(
        {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
    )

# ==========================================
# 🔐 MOBILE APP API ENDPOINTS
# ==========================================
class LoginRequest(BaseModel):
    email: str
    password: str

@router.post("/api/volco/login")
def mobile_login(request: LoginRequest):
    print(f"🔐 Login attempt for: {request.email}")
    user = authenticate_mobile_user(request.email, request.password)
    if user:
        return {"success": True, "user_id": user['id'], "name": user['name']}
    else:
        raise HTTPException(status_code=401, detail="Invalid email or password")