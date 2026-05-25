import os
import re
import asyncio
import subprocess
import json
import uuid
import numpy as np
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

# Import DB and Memory functions from root
from db import save_message
from vector_store import add_memory

action_engine = ActionEngine()
router = APIRouter()

# ⚡ THE FIX: Memory Locks to prevent Python from Garbage Collecting our connections
active_connections = set()
active_channels = set()
user_interrupt_flags = {}

# ==========================================
# ⚙️ CONFIGURATION & PATHS
# ==========================================
BASE_MODELS_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "models"))
# On macOS, Piper is a binary (no .exe)
PIPER_EXE = os.path.join(BASE_MODELS_PATH, "piper", "piper")
VOICE_MODEL = os.path.join(BASE_MODELS_PATH, "tts-piper", "en_US-lessac-medium.onnx")

# ==========================================
# 🗣️ TEXT TO SPEECH (Piper)
# ==========================================
def generate_piper_pcm(text: str) -> bytes:
    if not text.strip(): return b""
    
    # ⚡ Check if paths exist
    if not os.path.exists(PIPER_EXE):
        print(f"❌ [TTS ERROR] Piper executable not found at: {PIPER_EXE}")
        return b""
    if not os.path.exists(VOICE_MODEL):
        print(f"❌ [TTS ERROR] Voice model not found at: {VOICE_MODEL}")
        return b""

    command = [PIPER_EXE, "--model", VOICE_MODEL, "--output-raw"]
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout_data, stderr_data = process.communicate(input=text.encode('utf-8'))
        
        if not stdout_data:
            print(f"⚠️ [TTS WARNING] Piper returned no audio. Stderr: {stderr_data.decode('utf-8', 'ignore')}")
            return b""
            
        return stdout_data
    except Exception as e: 
        print(f"❌ [TTS ERROR] subprocess failure: {e}")
        return b""

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
    """Speaks a message by splitting it into sentences for faster CPU delivery."""
    # ⚡ Ensure interrupts from previous turns are cleared
    user_interrupt_flags[user_id] = False
    
    await volco_manager.broadcast_to_app(user_id, {"role": "ai_start", "content": ""})
    await volco_manager.broadcast_to_app(user_id, {"role": "ai_token", "content": text})
    
    # ⚡ SPLIT INTO SENTENCES: Faster than generating the whole block on CPU
    sentence_endings = re.compile(r'(?<=[.!?¡¿,;])\s+')
    sentences = sentence_endings.split(text)
    
    for sentence in sentences:
        if not sentence.strip(): continue
        if user_interrupt_flags.get(user_id, False): break
        
        pcm = await asyncio.to_thread(generate_piper_pcm, sentence)
        if pcm: 
            await send_pcm_in_chunks(channel, pcm, user_id) 
        
    await volco_manager.broadcast_to_app(user_id, {"role": "ai_end", "content": ""})

async def stream_audio_response_rtc(prompt: str, channel, user_id: str) -> str:
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
        return buffer
    except Exception as e: 
        print(f"\n❌ Stream Error: {repr(e)}") 
        return ""

# ==========================================
# 🧠 THE AI BRAIN 
# ==========================================
async def process_voice_commit_text(text: str, channel, user_id: str, session_id: str):
    print(f"🗣️ {user_id}: {text}")

    if text:
        # 1. Save User Message to DB
        save_message(session_id, user_id, "user", text, title="Volco Voice Session")
        add_memory(text, user_id)

        await volco_manager.broadcast_to_app(user_id, {"role": "user", "content": text})
        
        # ⚡ THE FIX: Unpack 3 values (is_command, voice_text, and the payload)
        is_command, response_text, payload = action_engine.execute(text)

        if is_command:
            print(f"🤖 Action Executed: {response_text}")
            
            # ⚡ NEW: If the engine returned a Spotify command, send it to the Pi!
            if payload and channel.readyState == "open":
                channel.send(json.dumps(payload))
                print(f"📡 Sent JSON Command to Headset: {payload}")
                # ⚡ DELAY: Give the headset a moment to process the command before audio hits
                await asyncio.sleep(0.3) 

            await speak_simple_message(response_text, channel, user_id)
            
            # Save Command Response to DB
            save_message(session_id, user_id, "model", response_text)
            add_memory(response_text, user_id)
        else:
            full_ai_response = await stream_audio_response_rtc(text, channel, user_id)
            if full_ai_response.strip():
                save_message(session_id, user_id, "model", full_ai_response)
                add_memory(full_ai_response, user_id)

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
        
        # ⚡ Generate a session ID for this voice session
        session_id = str(uuid.uuid4())
        
        # ⚡ Processing state
        state = {
            "is_processing": False,
            "is_running": True,
            "last_processed_len": 0,
            "latest_transcript": ""
        }

        # ⚡ BACKGROUND STREAMING STT (Lower frequency on CPU)
        async def streaming_stt_loop():
            while state["is_running"]:
                await asyncio.sleep(0.8) # ⚡ Slightly slower loop to save CPU for generation
                
                if state["is_processing"]: continue
                
                # Only transcribe if we have new audio (at least 6400 bytes / 200ms)
                current_len = len(audio_buffer)
                if current_len > state["last_processed_len"] + 6400:
                    state["last_processed_len"] = current_len
                    try:
                        # Convert to numpy in thread to keep loop fast
                        buf_copy = bytearray(audio_buffer)
                        audio_np = np.frombuffer(buf_copy, dtype=np.int16).astype(np.float32) / 32768.0
                        
                        # ⚡ ACCURACY FIX: Re-enable VAD filter even in background
                        segments, _ = await asyncio.to_thread(
                            whisper_model.transcribe, 
                            audio_np, 
                            beam_size=1, 
                            language="en",
                            vad_filter=True,
                            vad_parameters=dict(min_silence_duration_ms=500)
                        )
                        text = " ".join([s.text for s in segments]).strip()
                        
                        if text:
                            state["latest_transcript"] = text
                            await volco_manager.broadcast_to_app(user_id, {"role": "user_partial", "content": text})
                    except Exception as e:
                        print(f"Streaming STT Error: {e}")

        # Start the loop
        asyncio.create_task(streaming_stt_loop())

        @channel.on("message")
        def on_message(message):
            nonlocal audio_buffer
            
            if isinstance(message, bytes):
                audio_buffer.extend(message)
                
            elif isinstance(message, str):
                if message == "PING": pass 
                elif message == "CLEAR":
                    audio_buffer = bytearray()
                    state["last_processed_len"] = 0
                    state["latest_transcript"] = ""
                elif message == "COMMIT":
                    if not state["is_processing"]:
                        state["is_processing"] = True
                        asyncio.create_task(wrapped_process_commit())
                # ⚡ NEW: CATCH THE KILL SIGNAL
                elif message == "INTERRUPT":
                    print(f"\n🛑 [SERVER] Interrupt received! Killing LLM & TTS for {user_id}...")
                    user_interrupt_flags[user_id] = True
                    asyncio.create_task(
                        volco_manager.broadcast_to_app(user_id, {"role": "ai_end", "content": ""})
                    )

        async def wrapped_process_commit():
            nonlocal audio_buffer
            
            # ⚡ INSTANT COMMIT: Use background transcript if available
            final_text = state["latest_transcript"]
            
            # ⚡ ACCURACY FIX: Final pass is more robust (higher beam size)
            # Only skip if we have a recent background transcript (less than 1sec extra audio)
            if not final_text or len(audio_buffer) > state["last_processed_len"] + 8000:
                print("⚡ [COMMIT] Running high-accuracy transcription pass...")
                buf_to_process = bytearray(audio_buffer)
                audio_np = np.frombuffer(buf_to_process, dtype=np.int16).astype(np.float32) / 32768.0
                segments, _ = await asyncio.to_thread(
                    whisper_model.transcribe, 
                    audio_np, 
                    beam_size=2, # ⚡ Increased for final accuracy
                    language="en", 
                    vad_filter=True
                )
                final_text = " ".join([s.text for s in segments]).strip()

            audio_buffer = bytearray() # Clear early
            state["last_processed_len"] = 0
            state["latest_transcript"] = ""
            
            await process_voice_commit_text(final_text, channel, user_id, session_id)
            state["is_processing"] = False

    @pc.on("connectionstatechange") 
    async def on_connectionstatechange():
        print(f"📶 [WEBRTC] Connection state: {pc.connectionState}")
        if pc.connectionState in ["failed", "closed"]:
            active_connections.discard(pc)
            # ⚡ Stop the background STT loop
            # We can't easily reach 'state' here unless we store it
            # But the loop checks pc.connectionState if we add it

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
