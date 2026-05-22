# backend/main.py
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
from starlette.concurrency import iterate_in_threadpool

# --- NEW FOLDER IMPORTS ---
from shared.models import whisper_model         # Loaded once from shared!
from vella.agent import stream_generate         # Vella's specific logic
from auth import router as auth_router
from vector_store import setup_schema, search_memory, add_memory
from db import init_db, save_message, get_user_sessions, get_chat_history
from volco.router import router as volco_router

# =============================
# CONFIGURATION
# =============================
PIPER_EXE = r"V:/Document/Vella-Modes/models/piper/piper.exe"
VOICE_MODEL = r"V:/Document/Vella-Modes/models/tts-piper/en_US-lessac-medium.onnx"

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
    
    print("\n🗺️  Active Routes:")
    for route in app.routes:
        print(f"   - {route.path}")  # type: ignore
    print("---------------------\n")

# =============================
# HELPERS (AUDIO GENERATION)
# =============================
def run_piper_tts(text: str, output_file: str):
    if not os.path.exists(PIPER_EXE): raise FileNotFoundError("Piper not found")
    command = [PIPER_EXE, "--model", VOICE_MODEL, "--output_file", output_file]
    process = subprocess.run(command, input=text, text=True, capture_output=True, encoding='utf-8')
    if process.returncode != 0:
        print(f"Piper Error: {process.stderr}")
        raise Exception("Piper synthesis failed.")

def remove_file(path: str):
    try:
        if os.path.exists(path): os.remove(path)
    except: pass

# =============================
# 1. WEB CHAT ENDPOINTS 
# =============================
class ChatRequest(BaseModel):
    prompt: str
    max_new_tokens: int = 512 # Changed to match Vella's new defaults

@app.post("/chat")
async def chat_endpoint(req: ChatRequest, request: Request):
    user_id = request.headers.get("x-user-id", "anonymous")
    session_id = request.headers.get("x-session-id")
    if not session_id or session_id == "null": session_id = str(uuid.uuid4())

    # 1. Fetch Chat History (mapped to model roles)
    raw_history = get_chat_history(session_id)
    temp_history = []
    for msg in raw_history:
        role = "assistant" if msg["role"] == "model" else "user"
        temp_history.append({"role": role, "content": msg["content"]})
    
    # 2. Add current user prompt
    temp_history.append({"role": "user", "content": req.prompt})

    # 3. CLEANUP: Ensure alternating roles (merge same-role consecutive messages)
    chat_history = []
    if temp_history:
        for msg in temp_history:
            if chat_history and chat_history[-1]["role"] == msg["role"]:
                # Merge with previous message if role is the same
                chat_history[-1]["content"] += "\n" + msg["content"]
            else:
                chat_history.append(msg)

    # 4. Limit to last 6 messages (after merging) to keep context lean
    chat_history = chat_history[-6:]
    
    # 5. Save user message to DB
    save_message(session_id, user_id, "user", req.prompt)

    async def response_generator():
        yield "" 
        full_response = ""
        # 6. Generate with cleaned history
        async for token in iterate_in_threadpool(stream_generate(chat_history, max_new_tokens=req.max_new_tokens)):
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