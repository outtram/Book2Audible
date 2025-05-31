#!/usr/bin/env python3
"""
FastAPI Web Interface for Book2Audible
"""
import os
import sys
import uuid
import asyncio
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import shutil
import tempfile
import logging

from fastapi import FastAPI, File, UploadFile, HTTPException, WebSocket, WebSocketDisconnect, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.websockets import WebSocketState
from pydantic import BaseModel
import uvicorn

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.core.processor import Book2AudioProcessor
from src.core.config import config
from src.utils.logger import setup_logger

# Web API Models
class ConversionRequest(BaseModel):
    voice: str = "tara"
    provider: str = "fal"
    manual_chapters: Optional[List[str]] = None

class ConversionStatus(BaseModel):
    job_id: str
    status: str  # pending, processing, completed, failed
    progress: float  # 0.0 to 1.0
    current_step: str
    chapters: List[Dict[str, Any]]
    error_message: Optional[str] = None
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None

class ChapterInfo(BaseModel):
    number: int
    title: str
    audio_file: Optional[str] = None
    text_file: Optional[str] = None
    verification_passed: bool = False
    duration_ms: int = 0

# Global job storage (in production, use Redis or database)
active_jobs: Dict[str, ConversionStatus] = {}
job_websockets: Dict[str, List[WebSocket]] = {}

app = FastAPI(
    title="Book2Audible Web API",
    description="Convert books to audiobooks using Orpheus TTS",
    version="1.0.0"
)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],  # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup logging
logger = setup_logger("WebAPI", config.log_file, "INFO")

# Serve static files (generated audio files)
app.mount("/static", StaticFiles(directory="data/output"), name="static")

@app.get("/")
async def root():
    """API health check"""
    return {"message": "Book2Audible Web API", "status": "running"}

@app.get("/api/voices")
async def get_voices():
    """Get available voices for TTS"""
    return {
        "fal": ["tara", "leah", "jess", "leo", "dan", "mia", "zac", "zoe"]
    }

@app.get("/api/providers")
async def get_providers():
    """Get available TTS providers"""
    return {
        "providers": [
            {
                "id": "fal",
                "name": "Fal.ai",
                "description": "Reliable Orpheus TTS with 8 voices",
                "pricing": "$0.05 per 1000 characters",
                "voices": 8,
                "recommended": True
            }
        ]
    }

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload and validate book file"""
    
    # Validate file type
    allowed_extensions = {'.txt', '.docx'}
    file_extension = Path(file.filename).suffix.lower()
    
    if file_extension not in allowed_extensions:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid file type. Allowed: {', '.join(allowed_extensions)}"
        )
    
    # Check file size (10MB limit)
    content = await file.read()
    if len(content) > 10 * 1024 * 1024:  # 10MB
        raise HTTPException(status_code=400, detail="File too large. Maximum size: 10MB")
    
    # Create unique job ID and temp directory
    job_id = str(uuid.uuid4())
    temp_dir = Path(tempfile.gettempdir()) / "book2audible" / job_id
    temp_dir.mkdir(parents=True, exist_ok=True)
    
    # Save uploaded file
    file_path = temp_dir / file.filename
    with open(file_path, 'wb') as f:
        f.write(content)
    
    # Basic file validation (try to read it)
    try:
        if file_extension == '.txt':
            with open(file_path, 'r', encoding='utf-8') as f:
                text_content = f.read()
        else:  # .docx
            # Let the processor handle docx files
            text_content = "DOCX file uploaded successfully"
            
        word_count = len(text_content.split())
        char_count = len(text_content)
        
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to read file: {str(e)}")
    
    logger.info(f"File uploaded: {file.filename} ({char_count} chars, {word_count} words)")
    
    # Store upload metadata for later retrieval
    upload_metadata = {
        "job_id": job_id,
        "filename": file.filename,
        "file_size": len(content),
        "character_count": char_count,
        "word_count": word_count,
        "estimated_cost_fal": round((char_count / 1000) * 0.05, 2),
        "upload_time": datetime.now().isoformat()
    }
    
    # Save metadata to file for persistence
    metadata_file = temp_dir / "upload_metadata.json"
    with open(metadata_file, 'w') as f:
        json.dump(upload_metadata, f, indent=2)
    
    return upload_metadata

@app.get("/api/upload/{job_id}")
async def get_upload_info(job_id: str):
    """Get upload information for a job"""
    
    # Try to find upload metadata
    temp_dir = Path(tempfile.gettempdir()) / "book2audible" / job_id
    metadata_file = temp_dir / "upload_metadata.json"
    
    if metadata_file.exists():
        try:
            with open(metadata_file, 'r') as f:
                upload_data = json.load(f)
            return upload_data
        except Exception as e:
            logger.error(f"Failed to read upload metadata for {job_id}: {e}")
    
    # If metadata file doesn't exist, try to get info from temp directory
    if temp_dir.exists():
        uploaded_files = list(temp_dir.glob("*"))
        if uploaded_files:
            # Find the uploaded file (not metadata)
            uploaded_file = None
            for file_path in uploaded_files:
                if file_path.name != "upload_metadata.json":
                    uploaded_file = file_path
                    break
            
            if uploaded_file:
                try:
                    file_size = uploaded_file.stat().st_size
                    
                    # Try to read content for character/word count
                    with open(uploaded_file, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    char_count = len(content)
                    word_count = len(content.split())
                    
                    return {
                        "job_id": job_id,
                        "filename": uploaded_file.name,
                        "file_size": file_size,
                        "character_count": char_count,
                        "word_count": word_count,
                        "estimated_cost_fal": round((char_count / 1000) * 0.05, 2),
                        "upload_time": None
                    }
                except Exception as e:
                    logger.error(f"Failed to analyze uploaded file for {job_id}: {e}")
    
    raise HTTPException(status_code=404, detail="Upload information not found")

@app.post("/api/convert/{job_id}")
async def start_conversion(job_id: str, request: ConversionRequest, background_tasks: BackgroundTasks):
    """Start book conversion process"""
    
    # Find uploaded file
    temp_dir = Path(tempfile.gettempdir()) / "book2audible" / job_id
    if not temp_dir.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Find the uploaded file
    uploaded_files = list(temp_dir.glob("*"))
    if not uploaded_files:
        raise HTTPException(status_code=404, detail="No uploaded file found")
    
    input_file = uploaded_files[0]
    
    # Create output directory
    output_dir = Path("data/output") / job_id
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Initialize job status
    job_status = ConversionStatus(
        job_id=job_id,
        status="pending",
        progress=0.0,
        current_step="Initializing...",
        chapters=[],
        start_time=datetime.now()
    )
    active_jobs[job_id] = job_status
    
    # Start processing in background
    background_tasks.add_task(
        process_book_background,
        job_id,
        input_file,
        output_dir,
        request.voice,
        request.provider,
        request.manual_chapters
    )
    
    logger.info(f"Conversion started: {job_id} with provider {request.provider}")
    
    return {"job_id": job_id, "status": "started"}

async def process_book_background(
    job_id: str,
    input_file: Path,
    output_dir: Path,
    voice: str,
    provider: str,
    manual_chapters: Optional[List[str]]
):
    """Background task to process the book"""
    
    try:
        # Update status
        await update_job_status(job_id, "processing", 0.1, "Initializing processor...")
        
        # Initialize processor
        processor = Book2AudioProcessor("INFO", provider)
        
        # Custom logger to capture progress
        class WebProgressLogger:
            def __init__(self, job_id: str):
                self.job_id = job_id
                self.current_chapter = 0
                self.total_chapters = 0
            
            def info(self, message: str):
                asyncio.create_task(self.handle_log_message(message))
            
            def error(self, message: str):
                asyncio.create_task(self.handle_log_message(f"ERROR: {message}"))
            
            def warning(self, message: str):
                asyncio.create_task(self.handle_log_message(f"WARNING: {message}"))
            
            def debug(self, message: str):
                asyncio.create_task(self.handle_log_message(f"DEBUG: {message}"))
            
            def setLevel(self, level):
                # No-op for web logger since we want all messages
                pass
            
            async def handle_log_message(self, message: str):
                # Parse progress from log messages
                if "Found" in message and "chapters" in message:
                    try:
                        parts = message.split()
                        self.total_chapters = int(parts[1])
                        await update_job_status(self.job_id, "processing", 0.2, f"Found {self.total_chapters} chapters")
                    except:
                        pass
                
                elif "completed successfully" in message and "%" in message:
                    try:
                        # Extract percentage from message like "✅ Chunk 5/24 completed successfully (20.8% done)"
                        import re
                        match = re.search(r'(\d+)/(\d+).*?(\d+\.\d+)%', message)
                        if match:
                            current_chunk = int(match.group(1))
                            total_chunks = int(match.group(2))
                            chapter_progress = float(match.group(3)) / 100
                            
                            # Calculate overall progress
                            if self.total_chapters > 0:
                                chapter_base_progress = (self.current_chapter / self.total_chapters) * 0.8
                                chapter_current_progress = (chapter_progress / self.total_chapters) * 0.8
                                overall_progress = 0.2 + chapter_base_progress + chapter_current_progress
                                
                                await update_job_status(
                                    self.job_id,
                                    "processing", 
                                    min(overall_progress, 0.95),
                                    f"Chapter {self.current_chapter + 1}: Processing chunk {current_chunk}/{total_chunks}"
                                )
                    except:
                        pass
                
                elif "Processing completed!" in message:
                    await update_job_status(self.job_id, "processing", 0.95, "Finalizing audio files...")
        
        # Set up custom logging
        web_logger = WebProgressLogger(job_id)
        processor.logger = web_logger
        
        await update_job_status(job_id, "processing", 0.15, "Starting text processing...")
        
        # Process the book
        result = processor.process_book(
            input_file,
            output_dir,
            manual_chapters
        )
        
        # Extract chapter information
        chapters = []
        if 'chapter_details' in result:
            for chapter_detail in result['chapter_details']:
                if 'audio_file' in chapter_detail:
                    # Make audio file path relative to static serving
                    audio_file = str(Path(chapter_detail['audio_file']).relative_to(Path("data/output")))
                    
                    chapters.append({
                        "number": chapter_detail.get('chapter', 0),
                        "title": chapter_detail.get('title', f"Chapter {chapter_detail.get('chapter', 0)}"),
                        "audio_file": f"/static/{audio_file}",
                        "verification_passed": chapter_detail.get('content_verification', {}).get('is_verified', False),
                        "duration_ms": 0  # Would need to calculate from audio file
                    })
        
        # Update final status
        if job_id in active_jobs:
            active_jobs[job_id].status = "completed"
            active_jobs[job_id].progress = 1.0
            active_jobs[job_id].current_step = "Conversion completed!"
            active_jobs[job_id].chapters = chapters
            active_jobs[job_id].end_time = datetime.now()
        
        # Notify WebSocket clients
        await broadcast_job_update(job_id)
        
        logger.info(f"Conversion completed: {job_id}")
        
    except Exception as e:
        logger.error(f"Conversion failed for {job_id}: {e}")
        
        if job_id in active_jobs:
            active_jobs[job_id].status = "failed"
            active_jobs[job_id].error_message = str(e)
            active_jobs[job_id].end_time = datetime.now()
            
            await broadcast_job_update(job_id)

async def update_job_status(job_id: str, status: str, progress: float, step: str):
    """Update job status and notify WebSocket clients"""
    if job_id in active_jobs:
        active_jobs[job_id].status = status
        active_jobs[job_id].progress = progress
        active_jobs[job_id].current_step = step
        
        await broadcast_job_update(job_id)

async def broadcast_job_update(job_id: str):
    """Broadcast job update to all connected WebSocket clients"""
    if job_id in job_websockets:
        job_data = active_jobs[job_id].dict()
        
        # Remove disconnected WebSockets
        connected_sockets = []
        for websocket in job_websockets[job_id]:
            if websocket.client_state == WebSocketState.CONNECTED:
                try:
                    await websocket.send_json(job_data)
                    connected_sockets.append(websocket)
                except:
                    pass  # WebSocket disconnected
        
        job_websockets[job_id] = connected_sockets

async def restore_job_from_files(job_id: str) -> Optional[ConversionStatus]:
    """Restore job status from completed files if available"""
    
    # Check if output directory exists
    output_dir = Path("data/output") / job_id
    if not output_dir.exists():
        return None
    
    # Look for processing log
    log_file = None
    for log_file_path in output_dir.glob("*_log.json"):
        log_file = log_file_path
        break
    
    if not log_file or not log_file.exists():
        return None
    
    try:
        with open(log_file, 'r') as f:
            log_data = json.load(f)
        
        # Extract chapter information
        chapters = []
        if 'chapter_details' in log_data:
            for chapter_detail in log_data['chapter_details']:
                if 'audio_file' in chapter_detail:
                    # Make audio file path relative to static serving
                    audio_file = str(Path(chapter_detail['audio_file']).relative_to(Path("data/output")))
                    
                    chapters.append({
                        "number": chapter_detail.get('chapter', 0),
                        "title": chapter_detail.get('title', f"Chapter {chapter_detail.get('chapter', 0)}"),
                        "audio_file": f"/static/{audio_file}",
                        "verification_passed": chapter_detail.get('content_verification', {}).get('is_verified', False),
                        "duration_ms": chapter_detail.get('quality_check', {}).get('duration_ms', 0)
                    })
        
        # Create completed job status
        job_status = ConversionStatus(
            job_id=job_id,
            status="completed",
            progress=1.0,
            current_step="Conversion completed!",
            chapters=chapters,
            start_time=datetime.fromisoformat(log_data.get('processing_date', datetime.now().isoformat().replace('T', ' '))),
            end_time=datetime.fromisoformat(log_data.get('processing_date', datetime.now().isoformat().replace('T', ' ')))
        )
        
        return job_status
        
    except Exception as e:
        logger.error(f"Failed to restore job {job_id} from files: {e}")
        return None

@app.get("/api/status/{job_id}")
async def get_job_status(job_id: str):
    """Get current status of conversion job"""
    
    # Check active jobs first
    if job_id in active_jobs:
        return active_jobs[job_id].dict()
    
    # Try to restore from completed files
    restored_job = await restore_job_from_files(job_id)
    if restored_job:
        # Add to active jobs for future requests
        active_jobs[job_id] = restored_job
        return restored_job.dict()
    
    raise HTTPException(status_code=404, detail="Job not found")

@app.websocket("/ws/{job_id}")
async def websocket_endpoint(websocket: WebSocket, job_id: str):
    """WebSocket endpoint for real-time progress updates"""
    
    await websocket.accept()
    
    # Add to job WebSocket list
    if job_id not in job_websockets:
        job_websockets[job_id] = []
    job_websockets[job_id].append(websocket)
    
    try:
        # Send current status immediately
        if job_id in active_jobs:
            await websocket.send_json(active_jobs[job_id].dict())
        
        # Keep connection alive and handle messages
        while True:
            data = await websocket.receive_text()
            # Echo back for connection testing
            await websocket.send_text(f"Received: {data}")
            
    except WebSocketDisconnect:
        # Remove from job WebSocket list
        if job_id in job_websockets:
            try:
                job_websockets[job_id].remove(websocket)
            except ValueError:
                pass

@app.get("/api/download/{job_id}")
async def download_all_chapters(job_id: str):
    """Download all chapters as a ZIP file"""
    
    if job_id not in active_jobs or active_jobs[job_id].status != "completed":
        raise HTTPException(status_code=404, detail="Job not found or not completed")
    
    # Create ZIP file with all chapters
    import zipfile
    
    output_dir = Path("data/output") / job_id
    zip_path = output_dir / f"{job_id}_audiobook.zip"
    
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for audio_file in output_dir.glob("*.wav"):
            zipf.write(audio_file, audio_file.name)
    
    return FileResponse(
        zip_path,
        media_type='application/zip',
        filename=f"audiobook_{job_id}.zip"
    )

@app.get("/api/test-connection")
async def test_tts_connection():
    """Test TTS provider connections with timeout"""
    
    results = {}
    
    # Test Fal.ai with timeout
    try:
        import asyncio
        from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError
        
        def test_fal_connection():
            try:
                from src.core.fal_tts_client import FalTTSClient
                fal_client = FalTTSClient()
                return fal_client.test_connection_detailed()
            except Exception as e:
                return {"success": False, "error": str(e)}
        
        # Run the test with a 10 second timeout
        with ThreadPoolExecutor() as executor:
            try:
                future = executor.submit(test_fal_connection)
                fal_result = await asyncio.wait_for(
                    asyncio.wrap_future(future), 
                    timeout=10.0
                )
                
                if isinstance(fal_result, dict):
                    if fal_result["error"]:
                        results["fal"] = {"status": "error", "message": fal_result["error"]}
                    elif fal_result["success"]:
                        results["fal"] = {"status": "success"}
                    else:
                        results["fal"] = {"status": "failed", "message": "Connection test returned false"}
                else:
                    results["fal"] = {"status": "success" if fal_result else "failed"}
                    
            except asyncio.TimeoutError:
                results["fal"] = {"status": "timeout", "message": "Connection test timed out after 10 seconds"}
                
    except Exception as e:
        results["fal"] = {"status": "error", "message": str(e)}
    
    return results

@app.get("/api/system-status")
async def get_system_status():
    """Get comprehensive system status"""
    import psutil
    import os
    from pathlib import Path
    
    try:
        # Check disk space
        disk_usage = psutil.disk_usage('/')
        
        # Check memory usage
        memory = psutil.virtual_memory()
        
        # Check if log file exists and get size
        log_file_path = Path("data/logs/book2audible.log")
        log_file_size = log_file_path.stat().st_size if log_file_path.exists() else 0
        
        # Check active jobs
        active_job_count = len(active_jobs)
        processing_jobs = len([job for job in active_jobs.values() if job.status == "processing"])
        
        # Check TTS connection
        tts_status = await test_tts_connection()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "system": {
                "disk_usage": {
                    "total_gb": round(disk_usage.total / (1024**3), 2),
                    "used_gb": round(disk_usage.used / (1024**3), 2),
                    "free_gb": round(disk_usage.free / (1024**3), 2),
                    "percent_used": round((disk_usage.used / disk_usage.total) * 100, 1)
                },
                "memory": {
                    "total_gb": round(memory.total / (1024**3), 2),
                    "used_gb": round(memory.used / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "percent_used": round(memory.percent, 1)
                }
            },
            "application": {
                "log_file_size_mb": round(log_file_size / (1024**2), 2),
                "active_jobs": active_job_count,
                "processing_jobs": processing_jobs,
                "tts_connection": tts_status
            },
            "directories": {
                "data_dir_exists": Path("data").exists(),
                "output_dir_exists": Path("data/output").exists(),
                "logs_dir_exists": Path("data/logs").exists()
            }
        }
    except Exception as e:
        return {"error": str(e), "timestamp": datetime.now().isoformat()}

@app.get("/api/logs")
async def get_logs(lines: int = 100):
    """Get recent log entries"""
    try:
        log_file_path = Path("data/logs/book2audible.log")
        if not log_file_path.exists():
            return {"logs": [], "message": "Log file not found"}
        
        # Read last N lines
        with open(log_file_path, 'r') as f:
            all_lines = f.readlines()
            recent_lines = all_lines[-lines:] if len(all_lines) > lines else all_lines
        
        # Parse logs into structured format
        logs = []
        for line in recent_lines:
            line = line.strip()
            if line:
                # Try to parse timestamp and level
                try:
                    parts = line.split(' - ', 3)
                    if len(parts) >= 4:
                        timestamp = parts[0]
                        logger_name = parts[1]
                        level_color = parts[2]
                        message = parts[3]
                        
                        # Extract level from colored text like [32mINFO[0m
                        import re
                        level_match = re.search(r'\[(\d+)m([A-Z]+)\[0m', level_color)
                        level = level_match.group(2) if level_match else "INFO"
                        
                        logs.append({
                            "timestamp": timestamp,
                            "logger": logger_name,
                            "level": level,
                            "message": message,
                            "raw": line
                        })
                    else:
                        logs.append({
                            "timestamp": "",
                            "logger": "",
                            "level": "INFO",
                            "message": line,
                            "raw": line
                        })
                except Exception:
                    logs.append({
                        "timestamp": "",
                        "logger": "",
                        "level": "INFO", 
                        "message": line,
                        "raw": line
                    })
        
        return {
            "logs": logs,
            "total_lines": len(recent_lines),
            "file_path": str(log_file_path)
        }
    except Exception as e:
        return {"error": str(e), "logs": []}

# Serve the React frontend (will be built later)
@app.get("/app", response_class=HTMLResponse)
async def serve_frontend():
    """Serve the React frontend"""
    return """
    <html>
        <head>
            <title>Book2Audible Web Interface</title>
        </head>
        <body>
            <h1>Book2Audible Web Interface</h1>
            <p>React frontend will be built here</p>
            <p>API is running at: <a href="/docs">/docs</a></p>
        </body>
    </html>
    """

if __name__ == "__main__":
    # Ensure output directory exists
    Path("data/output").mkdir(parents=True, exist_ok=True)
    
    # Run the FastAPI server
    uvicorn.run(
        "web_api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )