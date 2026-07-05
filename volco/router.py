import re
import asyncio
import json
import uuid
import io
import os
import numpy as np
import soundfile as sf
from fastapi import APIRouter, Request, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.concurrency import iterate_in_threadpool
from aiortc import RTCPeerConnection, RTCSessionDescription

# ⚡ IMPORT ALREADY LOADED MODELS FROM SHARED
from shared.models import whisper_model, kokoro_voice

# Import Volco-specific modules
from volco.connection import volco_manager
from volco.agent import stream_generate
from volco.asr_engine import ASRConfig, WhisperASREngine
from volco.state_machine import VoiceSessionStateMachine, log_voice_event
from volco.intent.classifier import IntentClassifier
from volco.intent.router import IntentRouter
from volco.actions.chat import CHAT_MODEL
from .db import authenticate_mobile_user

# Import DB and Memory functions from root
from db import save_message
from vector_store import add_memory

asr_engine = WhisperASREngine(whisper_model, ASRConfig(sample_rate=16000))
router = APIRouter()

# ⚡ Memory Locks to prevent Python from Garbage Collecting our connections
active_connections = set()
active_channels = set()


def get_tts_concurrency() -> int:
    try:
        return max(1, int(os.getenv("VOLCO_TTS_CONCURRENCY", "2")))
    except ValueError:
        return 2


# ==========================================
# 🗣️ TEXT TO SPEECH (Kokoro ONNX → WAV)
# ==========================================
def generate_kokoro_wav(text: str) -> bytes:
    """
    Synthesizes speech with Kokoro ONNX and returns a complete WAV file as bytes.
    The WAV starts with the standard RIFF header so the device can detect and
    play it directly without any extra framing.
    """
    text = text.strip()
    if not text:
        return b""

    if kokoro_voice is None:
        print("❌ [TTS ERROR] Kokoro voice engine is not available/initialized.")
        return b""

    try:
        audio_samples, sample_rate = kokoro_voice.create(
            text=text,
            voice="af_heart",
            speed=1.1,
            lang="en-us"
        )

        if audio_samples is None or len(audio_samples) == 0:
            print("⚠️ [TTS WARNING] Kokoro returned no audio.")
            return b""

        # Clamp float32 outputs safely before conversion
        audio_samples = np.clip(audio_samples, -1.0, 1.0)

        # Write into an in-memory WAV (RIFF header + PCM_16 body)
        wav_io = io.BytesIO()
        if len(audio_samples.shape) > 1:
            audio_samples = audio_samples.mean(axis=1)
        sf.write(wav_io, audio_samples, sample_rate, format="WAV", subtype="PCM_16")
        wav_io.seek(0)
        return wav_io.read()

    except Exception as e:
        print(f"❌ [TTS ERROR] Kokoro WAV synthesis failure: {e}")
        return b""


async def send_wav(channel, wav_data: bytes) -> None:
    """
    Send a complete WAV file as a single binary message over the WebRTC data channel.
    Each call is one self-contained WAV — the device detects the RIFF header and
    plays it immediately. WebRTC's SCTP layer handles fragmentation transparently.
    """
    if wav_data and channel.readyState == "open":
        channel.send(wav_data)
        await asyncio.sleep(0.01)  # Brief yield to the event loop


# ==========================================
# 🔄 TTS HELPERS
# ==========================================
async def speak_simple_message(text: str, channel, user_id: str) -> None:
    """
    Synthesize a complete short response as a single WAV and send it.
    Used for all intent action confirmations (Spotify, etc.).
    """
    await volco_manager.broadcast_to_app(user_id, {"role": "ai_start", "content": ""})
    await volco_manager.broadcast_to_app(user_id, {"role": "ai_token", "content": text})

    wav = await asyncio.to_thread(generate_kokoro_wav, text)
    if wav:
        await send_wav(channel, wav)

    await volco_manager.broadcast_to_app(user_id, {"role": "ai_end", "content": ""})


async def stream_audio_response_rtc(prompt: str, channel, user_id: str) -> str:
    """
    Stream LLM tokens while completed sentences are prepared as WAVs.
    The device queues the WAVs and plays them back-to-back for smooth speech.
    Returns the full response text.
    """
    buffer = ""
    full_response = ""
    sentence_endings = re.compile(r'(?<=[.!?¡¿,;])\s+')
    tts_semaphore = asyncio.Semaphore(get_tts_concurrency())
    tts_tasks: dict[int, asyncio.Task[bytes]] = {}
    tts_condition = asyncio.Condition()
    next_sentence_index = 0
    next_send_index = 0
    llm_done = False

    async def synthesize_sentence(sentence: str, index: int) -> bytes:
        async with tts_semaphore:
            try:
                wav = await asyncio.to_thread(generate_kokoro_wav, sentence)
                if wav:
                    print(f"🔊 [TTS] WAV ready #{index}", flush=True)
                return wav
            except Exception as e:
                print(f"❌ [TTS STREAM ERROR] sentence #{index}: {e}")
                return b""

    async def enqueue_sentence(sentence: str) -> None:
        nonlocal next_sentence_index

        sentence = sentence.strip()
        if not sentence:
            return

        async with tts_condition:
            index = next_sentence_index
            next_sentence_index += 1
            tts_tasks[index] = asyncio.create_task(synthesize_sentence(sentence, index))
            tts_condition.notify_all()

    async def send_ready_wavs_in_order() -> None:
        nonlocal next_send_index

        while True:
            async with tts_condition:
                await tts_condition.wait_for(
                    lambda: next_send_index in tts_tasks or (llm_done and next_send_index >= next_sentence_index)
                )
                if llm_done and next_send_index >= next_sentence_index:
                    return

                index = next_send_index
                task = tts_tasks[index]

            wav = await task
            if wav:
                await send_wav(channel, wav)
                # print(f"📤 [TTS] Sent WAV #{index} to Volco", flush=True)

            async with tts_condition:
                tts_tasks.pop(index, None)
                next_send_index += 1
                tts_condition.notify_all()

    sender_task = asyncio.create_task(send_ready_wavs_in_order())

    try:
        await volco_manager.broadcast_to_app(user_id, {"role": "ai_start", "content": ""})
        # print(f"🤖 Volco: ", end="", flush=True)

        async for token in iterate_in_threadpool(stream_generate(prompt, model=CHAT_MODEL)):
            buffer += token
            full_response += token
            # print(token, end="", flush=True)

            await volco_manager.broadcast_to_app(user_id, {"role": "ai_token", "content": token})

            parts = sentence_endings.split(buffer)
            if len(parts) > 1:
                # Send every complete sentence as its own WAV
                for sentence in parts[:-1]:
                    await enqueue_sentence(sentence)
                buffer = parts[-1]  # Keep the incomplete trailing fragment

        # Send whatever remains after the stream closes
        if buffer.strip():
            await enqueue_sentence(buffer)

        async with tts_condition:
            llm_done = True
            tts_condition.notify_all()

        await sender_task

        print()
        await volco_manager.broadcast_to_app(user_id, {"role": "ai_end", "content": ""})
        return full_response

    except Exception as e:
        print(f"\n❌ Stream Error: {repr(e)}")
        for task in tts_tasks.values():
            task.cancel()
        if not sender_task.done():
            sender_task.cancel()
            try:
                await sender_task
            except asyncio.CancelledError:
                pass
        return ""


# ==========================================
# 🧠 THE AI BRAIN
# ==========================================
async def process_voice_commit_text(text: str, channel, user_id: str, session_id: str):
    # print(f"🗣️ {user_id}: {text}")

    if text:
        keep_session_open = False

        # 1. Save User Message to DB
        save_message(session_id, user_id, "user", text, title="Volco Voice Session")
        add_memory(text, user_id)

        await volco_manager.broadcast_to_app(user_id, {"role": "user", "content": text})

        classifier = IntentClassifier()
        intent_data = await classifier.classify(text)
        intent = intent_data.get("intent", "conversation")
        action = intent_data.get("action", "call_llm")

        # print(f"🧠 Intent: {intent} | Action: {action}")

        if intent == "conversation" and action == "call_llm":
            response_text = await stream_audio_response_rtc(intent_data.get("text", text), channel, user_id)
            keep_session_open = bool(response_text.strip())

            if response_text:
                save_message(session_id, user_id, "model", response_text)
                add_memory(response_text, user_id)
        else:
            intent_router = IntentRouter()
            assistant_result = await intent_router.route(intent_data)
            response_text = assistant_result.get("message", "")
            payload = assistant_result.get("device_payload")
            keep_session_open = False

            # print(f"🧠 Action Result: {response_text}")

            if payload and channel.readyState == "open":
                channel.send(json.dumps(payload))
                # print(f"📡 Sent JSON Command to Headset: {payload}")
                await asyncio.sleep(0.3)

            if response_text:
                await speak_simple_message(response_text, channel, user_id)
                save_message(session_id, user_id, "model", response_text)
                add_memory(response_text, user_id)

        await asyncio.sleep(0.5)
        if channel.readyState == "open":
            channel.send(json.dumps({
                "action": "none",
                "continue_session": keep_session_open,
                "end_session": not keep_session_open,
            }))
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

        # print(f"⚡ [WEBRTC] UDP Channel '{channel.label}' opened for {user_id}")
        audio_buffer = bytearray()

        session_id = str(uuid.uuid4())
        voice_state = VoiceSessionStateMachine()

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
                if message.startswith("{"):
                    try:
                        json.loads(message)
                    except json.JSONDecodeError:
                        pass

                if message == "PING":
                    pass
                elif message == "CLEAR":
                    audio_buffer = bytearray()
                    voice_state.reset_to_idle("client_clear")
                elif message == "COMMIT":
                    if not state["is_processing"]:
                        state["is_processing"] = True
                        asyncio.create_task(wrapped_process_commit())

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
                    # print("🔇 [COMMIT] Ignored empty/no-speech commit.")
                    if channel.readyState == "open":
                        channel.send("NO_SPEECH")
                    voice_state.reset_to_idle("no_speech")
                    return

                voice_state.responding()
                await process_voice_commit_text(final_text, channel, user_id, session_id)
                voice_state.reset_to_idle("response_complete")
            except Exception as e:
                # print(f"❌ [ASR] Commit processing failed: {e}")
                if channel.readyState == "open":
                    channel.send("NO_SPEECH")
                voice_state.reset_to_idle("asr_error")
            finally:
                state["is_processing"] = False

    @pc.on("connectionstatechange")
    async def on_connectionstatechange():
        # print(f"📶 [WEBRTC] Connection state: {pc.connectionState}")
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
    # print(f"🔐 Login attempt for: {request.email}")
    user = authenticate_mobile_user(request.email, request.password)
    if user:
        return {"success": True, "user_id": user['id'], "name": user['name']}
    else:
        raise HTTPException(status_code=401, detail="Invalid email or password")
