import os
# Force offline mode for HuggingFace
os.environ["HF_HUB_OFFLINE"] = "1"
os.environ["TRANSFORMERS_OFFLINE"] = "1"

import time
import tempfile
import subprocess
import uuid
from fastapi import FastAPI, UploadFile, File, Request, BackgroundTasks
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from faster_whisper import WhisperModel
# 👇 1. NEW IMPORT FOR CONCURRENCY
from starlette.concurrency import iterate_in_threadpool

# --- CUSTOM IMPORTS ---
from chat_agent import generate, stream_generate 
from auth import router as auth_router
from vector_store import setup_schema, search_memory, add_memory
# NEW: Import Database functions
from db import init_db, save_message, get_user_sessions, get_chat_history

# =============================
# CONFIGURATION
# =============================
PIPER_EXE = r"V:/Document/Vella-Modes/models/piper/piper.exe"
VOICE_MODEL = r"V:/Document/Vella-Modes/models/tts-piper/en_US-lessac-medium.onnx"

# Load Whisper (STT)
print("Loading Whisper...")
whisper_model = WhisperModel(
    "V:/Document/Vella-Modes/models/models--Systran--faster-whisper-small/snapshots/536b0662742c02347bc0e980a01041f333bce120",
    device="cpu",
    compute_type="int8"
)

# =============================
# APP SETUP
# =============================
app = FastAPI(title="Vella Local Backend (Streaming + History)")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)

# --- STARTUP EVENTS ---
@app.on_event("startup")
def startup_event():
    # 1. Initialize Vector Store
    setup_schema()
    # 2. Initialize SQL Database (Create Tables)
    init_db()

# =============================
# HELPER: PIPER TTS ENGINE
# =============================
def run_piper_tts(text: str, output_file: str):
    if not os.path.exists(PIPER_EXE):
        raise FileNotFoundError(f"Piper executable not found at: {PIPER_EXE}")
    if not os.path.exists(VOICE_MODEL):
        raise FileNotFoundError(f"Voice model not found at: {VOICE_MODEL}")

    command = [
        PIPER_EXE,
        "--model", VOICE_MODEL,
        "--output_file", output_file
    ]
    
    try:
        process = subprocess.run(
            command,
            input=text,
            text=True,
            capture_output=True,
            encoding='utf-8' # Fix for special characters
        )
        
        if process.returncode != 0:
            print(f"Piper Error: {process.stderr}")
            raise Exception("Piper synthesis failed.")
            
    except Exception as e:
        print(f"Subprocess Error: {e}")
        raise e

def remove_file(path: str):
    try:
        if os.path.exists(path):
            os.remove(path)
    except Exception:
        pass

# =============================
# HISTORY ENDPOINTS (NEW)
# =============================

@app.get("/history/sessions")
def read_sessions(user_id: str):
    """Fetch list of previous chats for the sidebar"""
    return get_user_sessions(user_id)

@app.get("/history/{session_id}")
def read_chat_history(session_id: str):
    """Fetch messages for a specific chat"""
    return get_chat_history(session_id)

# =============================
# CHAT ENDPOINT (UPDATED)
# =============================

class ChatRequest(BaseModel):
    prompt: str
    max_new_tokens: int = 128

@app.post("/chat")
async def chat_endpoint(req: ChatRequest, request: Request):
    user_id = request.headers.get("x-user-id", "anonymous")
    # Get session ID from frontend, or generate one if missing
    session_id = request.headers.get("x-session-id")
    if not session_id or session_id == "null":
        session_id = str(uuid.uuid4())

    # 1. Save USER message to History DB
    # We do this immediately so even if generation fails, the prompt is saved
    save_message(session_id, user_id, "user", req.prompt)

    # 2. Generator for Streaming Response
    async def response_generator():
        yield "" 
        
        full_response = ""
        
        # 👇 3. THE FIX: Run blocking generator in a thread pool
        # This allows multiple devices to connect simultaneously
        async for token in iterate_in_threadpool(stream_generate(req.prompt, max_new_tokens=req.max_new_tokens)):
            full_response += token
            yield token 
        
        # 4. After generation: Save MODEL message to History DB
        if full_response.strip():
            # Save to SQL History
            save_message(session_id, user_id, "model", full_response)
            
            # Save to Vector Memory (for context recall)
            add_memory(req.prompt, user_id)
            add_memory(full_response, user_id)

    return StreamingResponse(response_generator(), media_type="text/plain")


# =============================
# SPEECH → TEXT (WHISPER)
# =============================
@app.post("/stt")
async def speech_to_text(audio: UploadFile = File(...)):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".webm") as tmp:
        tmp.write(await audio.read())
        audio_path = tmp.name

    try:
        segments, _ = whisper_model.transcribe(
            audio_path,
            language="en",
            vad_filter=True
        )
        text = " ".join(seg.text for seg in segments).strip()
        return {"text": text}

    except Exception as e:
        return {"text": "", "error": str(e)}

    finally:
        if os.path.exists(audio_path):
            os.remove(audio_path)

# =============================
# SIMPLE TTS ENDPOINT
# =============================
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

# =============================
# VOLCO: THE PIPELINE
# =============================
@app.post("/volco_process")
async def volco_process(
    background_tasks: BackgroundTasks, 
    audio: UploadFile = File(...),
    user_id: str = "volco_headset_01"
):
    print(f"\n--- Volco Request Received from {user_id} ---")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp:
        tmp.write(await audio.read())
        input_audio_path = tmp.name

    try:
        # 1. STT
        segments, _ = whisper_model.transcribe(input_audio_path, language="en")
        user_text = " ".join(seg.text for seg in segments).strip()
        
        if os.path.exists(input_audio_path):
            os.remove(input_audio_path)

        if not user_text:
            return JSONResponse({"error": "No speech detected"}, status_code=400)
        
        print(f" 🗣️ User: {user_text}")

        # 2. LLM (Blocking)
        full_prompt = f"User: {user_text}\nResponse:"
        raw_ai_reply = generate(full_prompt, max_new_tokens=64) 
        
        if "Response:" in raw_ai_reply:
            ai_reply = raw_ai_reply.split("Response:")[-1].strip()
        else:
            ai_reply = raw_ai_reply.strip()
            
        if "User:" in ai_reply:
            ai_reply = ai_reply.split("\n")[0].strip()

        print(f" 🤖 Vella: {ai_reply}")

        # 3. TTS
        os.makedirs("temp_audio", exist_ok=True)
        output_filename = f"temp_audio/volco_reply_{int(time.time())}.wav"
        output_path = os.path.join(os.getcwd(), output_filename)
        
        run_piper_tts(ai_reply, output_path)

        background_tasks.add_task(remove_file, output_path)
        return FileResponse(output_path, media_type="audio/wav", filename="reply.wav")

    except Exception as e:
        print(f"❌ ERROR: {e}")
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import uvicorn
    # Updated to port 8001
    uvicorn.run(app, host="0.0.0.0", port=8001)