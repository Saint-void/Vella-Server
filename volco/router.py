import re
import asyncio
import json
import uuid
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.concurrency import iterate_in_threadpool
from aiortc import RTCPeerConnection, RTCSessionDescription

# ⚡ IMPORT ALREADY LOADED MODELS FROM SHARED
from shared.models import whisper_model, piper_voice

# Import Volco-specific modules
from volco.connection import volco_manager
from volco.action_engine import ActionEngine
from volco.agent import stream_generate
from volco.asr_engine import ASRConfig, WhisperASREngine
from volco.state_machine import VoiceSessionStateMachine, log_voice_event
from .db import authenticate_mobile_user  

# Import DB and Memory functions from root
from db import save_message
from vector_store import add_memory

action_engine = ActionEngine()
asr_engine = WhisperASREngine(whisper_model, ASRConfig(sample_rate=16000))
router = APIRouter()

# ⚡ THE FIX: Memory Locks to prevent Python from Garbage Collecting our connections
active_connections = set()
active_channels = set()
user_interrupt_flags = {}

# ==========================================
# 🗣️ TEXT TO SPEECH (Piper)
# ==========================================
def generate_piper_pcm(text: str) -> bytes:
    text = text.strip()
    if not text:
        return b""

    try:
        audio_data = bytearray()
        for chunk in piper_voice.synthesize(text):
            audio_data.extend(chunk.audio_int16_bytes)

        if not audio_data:
            print("⚠️ [TTS WARNING] Piper returned no audio.")
            return b""

        return bytes(audio_data)
    except Exception as e: 
        print(f"❌ [TTS ERROR] Native Piper synthesis failure: {e}")
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
    connection_context = {"channel": None, "state": None, "voice_state": None}

    @pc.on("datachannel")
    def on_datachannel(channel):
        active_channels.add(channel) 
        
        print(f"⚡ [WEBRTC] UDP Channel '{channel.label}' opened for {user_id}")
        audio_buffer = bytearray()
        
        # ⚡ Generate a session ID for this voice session
        session_id = str(uuid.uuid4())
        voice_state = VoiceSessionStateMachine()
        
        # ⚡ Processing state
        state = {
            "is_processing": False,
            "is_running": True
        }
        connection_context["channel"] = channel
        connection_context["state"] = state
        connection_context["voice_state"] = voice_state

        @channel.on("message")
        def on_message(message):
            nonlocal audio_buffer
            
            if isinstance(message, bytes):
                if state["is_processing"]:
                    log_voice_event("noise_filtered", reason="audio_received_while_processing", bytes=len(message))
                    return
                if not audio_buffer:
                    voice_state.wake_word_detected()
                    voice_state.start_listening()
                audio_buffer.extend(message)
                
            elif isinstance(message, str):
                if message == "PING": pass 
                elif message == "CLEAR":
                    audio_buffer = bytearray()
                    voice_state.reset_to_idle("client_clear")
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
            try:
                buf_to_process = bytes(audio_buffer)
                audio_buffer = bytearray()
                log_voice_event("endpoint_triggered", source="client", bytes=len(buf_to_process))

                voice_state.processing_asr()
                final_text = await asyncio.to_thread(asr_engine.transcribe_pcm, buf_to_process)
                final_text = final_text.strip()

                if not final_text:
                    print("🔇 [COMMIT] Ignored empty/no-speech commit.")
                    if channel.readyState == "open":
                        channel.send("NO_SPEECH")
                    voice_state.reset_to_idle("no_speech")
                    return

                voice_state.responding()
                await process_voice_commit_text(final_text, channel, user_id, session_id)
                voice_state.reset_to_idle("response_complete")
            except Exception as e:
                print(f"❌ [ASR] Commit processing failed: {e}")
                if channel.readyState == "open":
                    channel.send("NO_SPEECH")
                voice_state.reset_to_idle("asr_error")
            finally:
                state["is_processing"] = False

    @pc.on("connectionstatechange") 
    async def on_connectionstatechange():
        print(f"📶 [WEBRTC] Connection state: {pc.connectionState}")
        if pc.connectionState in ["failed", "closed"]:
            active_connections.discard(pc)
            channel_ref = connection_context.get("channel")
            state_ref = connection_context.get("state")
            voice_state_ref = connection_context.get("voice_state")
            if state_ref:
                state_ref["is_running"] = False
            if channel_ref:
                active_channels.discard(channel_ref)
            if voice_state_ref:
                voice_state_ref.reset_to_idle("connection_closed")

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
