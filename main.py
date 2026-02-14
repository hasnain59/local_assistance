from fastapi import FastAPI, Request, File, UploadFile, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, Response
from contextlib import asynccontextmanager
import uvicorn
import logging
from pathlib import Path
import shutil
from datetime import datetime

from .orchestrator import HybridOrchestrator
from .call_handler import CallHandler
from .config import Config

# Setup logging
Config.setup_logging()
logger = logging.getLogger(__name__)

# Global orchestrator instance
orchestrator = None
call_handler = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    global orchestrator, call_handler
    logger.info("Starting Hybrid Assistant...")
    try:
        orchestrator = HybridOrchestrator()
        call_handler = CallHandler(orchestrator)
        logger.info("Orchestrator initialized")
    except Exception as e:
        logger.critical(f"Failed to initialize orchestrator: {e}")
        raise
    yield
    # Shutdown
    logger.info("Shutting down...")

app = FastAPI(
    title="Local-First AI Assistant",
    description="Privacy-first hybrid assistant for calls, tasks, and appointments",
    version="2.0.0",
    lifespan=lifespan
)

# ------------------- Health -------------------
@app.get("/health")
async def health():
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "models": {
            "stt": orchestrator.speech.stt_model is not None,
            "tts": orchestrator.speech.tts_voice is not None,
            "nlu": orchestrator.nlu.model is not None,
            "vision": orchestrator.vision.model is not None
        }
    }

# ------------------- Call Webhooks -------------------
@app.post("/webhook/incoming-call")
async def incoming_call(request: Request):
    return await call_handler.handle_incoming_call(request)

@app.post("/webhook/process-speech")
async def process_speech(request: Request):
    return await call_handler.process_speech(request)

# ------------------- Text Processing -------------------
@app.post("/api/process-text")
async def process_text(text: str, session_id: str = None, use_cloud: bool = False):
    """Process a text message (SMS, chat, etc.)."""
    result = await orchestrator.process_text(text, session_id, use_cloud)
    if result["success"]:
        return JSONResponse(result)
    else:
        raise HTTPException(status_code=500, detail=result["error"])

# ------------------- Image Upload -------------------
@app.post("/api/upload-image")
async def upload_image(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    task_id: int = None
):
    """Upload an image for analysis and optional task linking."""
    # Validate file type
    if not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Save locally
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_filename = f"{timestamp}_{file.filename}"
    file_path = Path("local_data/images") / safe_filename
    file_path.parent.mkdir(parents=True, exist_ok=True)
    
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        logger.info(f"Saved uploaded image to {file_path}")
    except Exception as e:
        logger.error(f"Failed to save image: {e}")
        raise HTTPException(status_code=500, detail="Could not save image")
    
    # Process in background to avoid timeout
    background_tasks.add_task(orchestrator.process_image, str(file_path), task_id)
    
    return JSONResponse({
        "message": "Image uploaded, processing in background",
        "file_path": str(file_path)
    })

# ------------------- Calendar Endpoints -------------------
@app.get("/api/calendar/availability")
async def check_availability(datetime_str: str, duration: int = 60):
    try:
        dt = datetime.fromisoformat(datetime_str)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime format")
    result = orchestrator.calendar.check_availability(dt, duration)
    return JSONResponse(result)

@app.post("/api/calendar/book")
async def book_appointment(appt: dict):
    # Validate required fields
    if "title" not in appt or "start_datetime" not in appt:
        raise HTTPException(status_code=400, detail="Missing title or start_datetime")
    try:
        dt = datetime.fromisoformat(appt["start_datetime"])
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid datetime")
    
    result = orchestrator.calendar.book_appointment(
        title=appt["title"],
        start_datetime=dt,
        duration=appt.get("duration", 60),
        attendees=appt.get("attendees", [])
    )
    if result["success"]:
        return JSONResponse(result)
    else:
        raise HTTPException(status_code=409, detail=result)

# ------------------- Task Endpoints -------------------
@app.get("/api/tasks/{task_id}/timeline")
async def task_timeline(task_id: int):
    timeline = orchestrator.tasks.get_task_timeline(task_id)
    return JSONResponse({"timeline": timeline})

# ------------------- Run -------------------
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=Config.HOST,
        port=Config.PORT,
        reload=Config.DEBUG,
        log_level=Config.LOG_LEVEL.lower()
    )
