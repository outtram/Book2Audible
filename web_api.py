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
    
    return {
        "job_id": job_id,
        "filename": file.filename,
        "file_size": len(content),
        "character_count": char_count,
        "word_count": word_count,
        "estimated_cost_fal": round((char_count / 1000) * 0.05, 2)
    }

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

@app.get("/api/status/{job_id}")
async def get_job_status(job_id: str):
    """Get current status of conversion job"""
    
    if job_id not in active_jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return active_jobs[job_id].dict()

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
    """Test TTS provider connections"""
    
    results = {}
    
    # Test Fal.ai only
    try:
        from src.core.fal_tts_client import FalTTSClient
        fal_client = FalTTSClient()
        fal_result = fal_client.test_connection()
        results["fal"] = {"status": "success" if fal_result else "failed"}
    except Exception as e:
        results["fal"] = {"status": "error", "message": str(e)}
    
    return results

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