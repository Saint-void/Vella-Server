import os
# Force offline mode for HuggingFace
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import time
import tempfile
import subprocess
import uuid
import re 
from fastapi import FastAPI, UploadFile, File, Request, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from faster_whisper import WhisperModel
from starlette.concurrency import iterate_in_threadpool

# --- CUSTOM IMPORTS ---
from chat_agent import generate, stream_generate 
from auth import router as auth_router
from volco_router import router as volco_router
from vector_store import setup_schema, search_memory, add_memory
from db import init_db, save_message, get_user_sessions, get_chat_history

# =============================
# CONFIGURATION
# =============================
PIPER_EXE = r"V:/Document/Vella-Modes/models/piper/piper.exe"
VOICE_MODEL = r"V:/Document/Vella-Modes/models/tts-piper/en_US-lessac-medium.onnx"

# Load Whisper
print("Loading Whisper...")
whisper_model = WhisperModel(
    "V:/Document/Vella-Modes/models/models--Systran--faster-whisper-small/snapshots/536b0662742c02347bc0e980a01041f333bce120",
    device="cpu",
    compute_type="int8"
)

app = FastAPI(title="Vella Unified Backend")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(volco_router)

@app.on_event("startup")
def startup_event():
    setup_schema()
    init_db()
    
    # --- DEBUG: PRINT ALL ROUTES ---
    print("\n🗺️  Active Routes:")
    for route in app.routes:
        print(f"   - {route.path}")
    print("---------------------\n")

# =============================
# HELPERS (AUDIO GENERATION)
# =============================

def run_piper_tts(text: str, output_file: str):
    """Generates a WAV file (For Web UI)"""
    if not os.path.exists(PIPER_EXE): raise FileNotFoundError("Piper not found")
    
    command = [PIPER_EXE, "--model", VOICE_MODEL, "--output_file", output_file]
    
    process = subprocess.run(command, input=text, text=True, capture_output=True, encoding='utf-8')
    if process.returncode != 0:
        print(f"Piper Error: {process.stderr}")
        raise Exception("Piper synthesis failed.")

def generate_piper_pcm(text: str) -> bytes:
    """Generates RAW AUDIO BYTES (For Volco Streaming)"""
    if not text.strip(): return b""
    
    command = [PIPER_EXE, "--model", VOICE_MODEL, "--output-raw"]
    
    try:
        process = subprocess.Popen(
            command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        stdout_data, stderr_data = process.communicate(input=text.encode('utf-8'))
        return stdout_data
    except Exception as e:
        print(f"Piper Stream Error: {e}")
        return b""

def remove_file(path: str):
    try:
        if os.path.exists(path): os.remove(path)
    except: pass

# =============================
# 1. WEB CHAT ENDPOINTS (RESTORED)
# =============================

class ChatRequest(BaseModel):
    prompt: str
    max_new_tokens: int = 128

@app.post("/chat")
async def chat_endpoint(req: ChatRequest, request: Request):
    user_id = request.headers.get("x-user-id", "anonymous")
    session_id = request.headers.get("x-session-id")
    if not session_id or session_id == "null": session_id = str(uuid.uuid4())

    # Save User Msg
    save_message(session_id, user_id, "user", req.prompt)

    async def response_generator():
        yield "" 
        full_response = ""
        # Stream text token by token
        async for token in iterate_in_threadpool(stream_generate(req.prompt, max_new_tokens=req.max_new_tokens)):
            full_response += token
            yield token 
        
        # Save Model Msg
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
# 2. WEB AUDIO ENDPOINTS (RESTORED)
# =============================

@app.post("/stt")
async def speech_to_text(audio: UploadFile = File(...)):
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

@app.post("/tts")
async def tts_endpoint(req: TTSRequest, background_tasks: BackgroundTasks):
    try:
        filename = f"tts_{int(time.time()*1000)}.wav"
        output_path = os.path.join(tempfile.gettempdir(), filename)
        run_piper_tts(req.text, output_path)
        background_tasks.add_task(remove_file, output_path)
        return FileResponse(output_path, media_type="audio/wav", filename="tts.wav")
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)