# backend/main.py
import os
import io
import time
import uuid
import numpy as np
import soundfile as sf
from contextlib import asynccontextmanager
from fastapi import FastAPI, UploadFile, File, Request, BackgroundTasks, HTTPException, Response 
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.concurrency import iterate_in_threadpool

# --- NEW FOLDER IMPORTS ---
from shared.models import (
    KOKORO_DEFAULT_LANG,
    KOKORO_DEFAULT_SPEED,
    KOKORO_DEFAULT_VOICE,
    kokoro_voice,
    whisper_model,
)  # 👈 Loaded once natively from shared!
from vella.agent import stream_generate         
from auth import router as auth_router
from vector_store import setup_schema, search_memory, add_memory
from db import init_db, save_message, get_user_sessions, get_chat_history
from volco.router import router as volco_router

# =============================
# LIFESPAN MANAGEMENT (Replaces on_event)
# =============================
@asynccontextmanager
async def lifespan(app: FastAPI):
    # Runs exactly on startup
    setup_schema()
    init_db()
    
    print("\n🗺️  Active Routes:")
    for route in app.routes:
        print(f"   - {route.path}")  # type: ignore
    print("---------------------\n")
    yield
    # Any teardown logic can be placed here if needed

app = FastAPI(title="Vella Unified Backend", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(volco_router)

# =============================
# HELPERS (AUDIO CLEANUP)
# =============================
def remove_file(path: str):
    try:
        if os.path.exists(path): os.remove(path)
    except: pass

# =============================
# 1. WEB CHAT ENDPOINTS 
# =============================
class ChatRequest(BaseModel):
    prompt: str
    max_new_tokens: int = 2048

@app.post("/chat")
async def chat_endpoint(req: ChatRequest, request: Request):
    user_id = request.headers.get("x-user-id", "anonymous")
    session_id = request.headers.get("x-session-id")
    if not session_id or session_id == "null": session_id = str(uuid.uuid4())

    raw_history = get_chat_history(session_id)
    temp_history = []
    for msg in raw_history:
        role = "assistant" if msg["role"] == "model" else "user"
        temp_history.append({"role": role, "content": msg["content"]})
    
    # Add current user prompt
    temp_history.append({"role": "user", "content": req.prompt})

    # --- CLEANUP: Ensure strict alternation and start with 'user' ---
    chat_history = []
    for msg in temp_history:
        if chat_history and chat_history[-1]["role"] == msg["role"]:
            # Merge consecutive messages of the same role
            chat_history[-1]["content"] += "\n" + msg["content"]
        else:
            chat_history.append(msg)
    
    # Limit context to last 6 messages. 
    chat_history = chat_history[-6:]

    # Ensure history starts with 'user' (llama_cpp requirement for most templates)
    while chat_history and chat_history[0]["role"] != "user":
        chat_history.pop(0)

    save_message(session_id, user_id, "user", req.prompt)

    async def response_generator():
        yield "" 
        full_response = ""
        max_new_tokens = max(1, min(req.max_new_tokens, 3072))
        async for token in iterate_in_threadpool(stream_generate(chat_history, max_new_tokens=max_new_tokens)):
            full_response += token
            yield token 
        
        if full_response.strip():
            save_message(session_id, user_id, "model", full_response)
            add_memory(req.prompt, user_id)
            add_memory(full_response, user_id)

    return StreamingResponse(response_generator(), media_type="text/plain")

@app.get("/history/sessions")
def read_sessions(user_id: str):
    return get_user_sessions(user_id)

@app.get("/history/{session_id}")
def read_chat_history(session_id: str):
    return get_chat_history(session_id)

# =============================
# 2. WEB AUDIO ENDPOINTS 
# =============================
@app.post("/stt")
async def speech_to_text(audio: UploadFile = File(...)):
    import tempfile
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        tmp.write(await audio.read())
        audio_path = tmp.name
    try:
        segments, _ = whisper_model.transcribe(audio_path, language="en")
        text = " ".join(seg.text for seg in segments).strip()
        return {"text": text}
    finally:
        remove_file(audio_path)

class TTSRequest(BaseModel):
    text: str
    voice: str | None = None
    speed: float | None = None
    lang: str | None = None

@app.post("/tts")
async def tts_endpoint(req: TTSRequest):
    try:
        if kokoro_voice is not None:
            speed = req.speed if req.speed is not None else KOKORO_DEFAULT_SPEED
            speed = max(0.5, min(speed, 2.0))
            audio_np, sample_rate = kokoro_voice.create(
                req.text,
                voice=req.voice or KOKORO_DEFAULT_VOICE,
                speed=speed,
                lang=req.lang or KOKORO_DEFAULT_LANG,
            )
        else:
            audio_data = bytearray()
            if not audio_data:
                raise HTTPException(status_code=500, detail="No audio data generated")

            audio_np = np.frombuffer(audio_data, dtype=np.int16)
            sample_rate = 22050

        wav_io = io.BytesIO()
        sf.write(wav_io, audio_np, sample_rate, format='WAV')
        wav_io.seek(0)

        # Return the valid WAV file as a response
        return Response(
            content=wav_io.read(), 
            media_type="audio/wav",
            headers={"Content-Disposition": f"attachment; filename=tts_{uuid.uuid4()}.wav"}
        )
        
    except Exception as e:
        import traceback
        print(f"❌ Critical TTS Failure Traceback:\n{traceback.format_exc()}")
        return JSONResponse(
            {"error": f"Native speech synthesis failed: {str(e)}"}, 
            status_code=500
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
