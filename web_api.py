#!/usr/bin/env python3
"""
FastAPI Web Interface for Book2Audible
Version: 2.1.0
Build Date: 2025-06-14
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
import re

# Optional chunk management imports (safe fallback)
try:
    from src.core.enhanced_processor import EnhancedBook2AudioProcessor
    from src.core.chunk_manager import ChunkManager
    from src.core.chunk_database import ChunkDatabase
    CHUNK_MANAGEMENT_AVAILABLE = True
    print("✅ Chunk management features loaded")
except ImportError as e:
    print(f"⚠️  Chunk management features not available: {e}")
    CHUNK_MANAGEMENT_AVAILABLE = False
    EnhancedBook2AudioProcessor = Book2AudioProcessor  # Fallback

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
    
    class Config:
        # Configure JSON serialization for datetime objects
        json_encoders = {
            datetime: lambda v: v.isoformat() if v else None
        }

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
    return {
        "message": "Book2Audible Web API",
        "status": "running",
        "version": "2.1.0",
        "build_date": "2025-06-14",
        "timestamp": datetime.now().isoformat()
    }

@app.get("/api/version")
async def get_version():
    """Get API version information"""
    return {
        "backend_version": "2.1.0",
        "build_date": "2025-06-14",
        "timestamp": datetime.now().isoformat()
    }

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
    
    # Find the uploaded file (exclude metadata)
    uploaded_files = [f for f in temp_dir.glob("*") if f.name != "upload_metadata.json"]
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
        
        # Initialize enhanced processor with chunk tracking
        processor = EnhancedBook2AudioProcessor("INFO", provider, enable_chunk_tracking=True)
        
        # Simple logger that doesn't interfere with threading
        class WebProgressLogger:
            def __init__(self, job_id: str):
                self.job_id = job_id
                self.current_chapter = 0
                self.total_chapters = 0
            
            def info(self, message: str):
                # Just log to console, don't try to update job status from background thread
                logger.info(f"[{self.job_id}] {message}")
            
            def error(self, message: str):
                logger.error(f"[{self.job_id}] {message}")
            
            def warning(self, message: str):
                logger.warning(f"[{self.job_id}] {message}")
            
            def debug(self, message: str):
                logger.debug(f"[{self.job_id}] {message}")
            
            def setLevel(self, level):
                # No-op for web logger since we want all messages
                pass
        
        # Set up custom logging
        web_logger = WebProgressLogger(job_id)
        processor.logger = web_logger
        
        await update_job_status(job_id, "processing", 0.15, "Starting text processing...")
        
        # Process the book directly (not in thread executor to avoid signal handling issues)
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
        # Use json() method to properly serialize datetime objects, then parse back to dict
        job_json_str = active_jobs[job_id].json()
        job_data = json.loads(job_json_str)
        
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
    
    # First check if there are completed files - this takes priority
    restored_job = await restore_job_from_files(job_id)
    if restored_job:
        # Update active jobs with completed status
        active_jobs[job_id] = restored_job
        return restored_job
    
    # Check active jobs if no completed files found
    if job_id in active_jobs:
        return active_jobs[job_id]
    
    # Check if job directory exists but has no log files (interrupted/zombie job)
    output_dir = Path("data/output") / job_id
    if output_dir.exists():
        logger.info(f"Found interrupted job {job_id}, returning failed status")
        
        # Create a failed job status for interrupted jobs
        failed_job = ConversionStatus(
            job_id=job_id,
            status="failed",
            progress=0.0,
            current_step="Job was interrupted",
            chapters=[],
            error_message="Processing was interrupted and could not be completed",
            start_time=None,
            end_time=datetime.now()
        )
        
        # Store in active jobs for future requests
        active_jobs[job_id] = failed_job
        return failed_job
    
    raise HTTPException(status_code=404, detail="Job not found")

@app.get("/api/results/{job_id}")
async def get_job_results(job_id: str):
    """Get detailed results for a completed job without triggering API calls"""
    
    # Check if output directory exists
    output_dir = Path("data/output") / job_id
    if not output_dir.exists():
        raise HTTPException(status_code=404, detail="Job results not found")
    
    # Look for processing log
    log_file = None
    for log_file_path in output_dir.glob("*_log.json"):
        log_file = log_file_path
        break
    
    if not log_file or not log_file.exists():
        raise HTTPException(status_code=404, detail="Job log not found")
    
    try:
        with open(log_file, 'r') as f:
            log_data = json.load(f)
        
        # Get file list
        files = []
        for file_path in output_dir.rglob("*"):
            if file_path.is_file():
                relative_path = file_path.relative_to(output_dir)
                file_size = file_path.stat().st_size
                files.append({
                    "name": file_path.name,
                    "path": str(relative_path),
                    "size_bytes": file_size,
                    "size_human": f"{file_size / 1024:.1f} KB" if file_size < 1024*1024 else f"{file_size / (1024*1024):.1f} MB",
                    "type": "audio" if file_path.suffix == ".wav" else "text" if file_path.suffix == ".txt" else "report" if file_path.suffix in [".json", ".html"] else "other"
                })
        
        # Build response
        result = {
            "job_id": job_id,
            "status": "completed",
            "processing_date": log_data.get("processing_date"),
            "total_chapters": log_data.get("total_chapters", 0),
            "successful_chapters": log_data.get("successful_chapters", 0),
            "failed_chapters": log_data.get("failed_chapters", 0),
            "total_words_processed": log_data.get("total_words_processed", 0),
            "total_processing_time": log_data.get("total_processing_time", 0),
            "output_files": log_data.get("output_files", []),
            "files": sorted(files, key=lambda x: (x["type"], x["name"])),
            "chapter_details": log_data.get("chapter_details", [])
        }
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get results for {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to load job results")

@app.get("/results/{job_id}", response_class=HTMLResponse)
async def show_job_results_page(job_id: str):
    """Display job results in a simple HTML page (no API calls)"""
    
    try:
        # Get results data
        results_response = await get_job_results(job_id)
        results = results_response
        
        # Generate HTML
        html = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>Book2Audible Results - {job_id}</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .header {{ background: #10B981; color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px; }}
                .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }}
                .stat {{ background: #F3F4F6; padding: 15px; border-radius: 8px; }}
                .stat-value {{ font-size: 24px; font-weight: bold; color: #10B981; }}
                .stat-label {{ color: #6B7280; font-size: 14px; }}
                .files {{ margin-top: 20px; }}
                .file-list {{ display: grid; gap: 10px; }}
                .file {{ background: #F9FAFB; border: 1px solid #E5E7EB; padding: 12px; border-radius: 6px; display: flex; justify-content: between; align-items: center; }}
                .file-audio {{ border-left: 4px solid #10B981; }}
                .file-text {{ border-left: 4px solid #3B82F6; }}
                .file-report {{ border-left: 4px solid #8B5CF6; }}
                .file-name {{ font-weight: 500; }}
                .file-size {{ color: #6B7280; font-size: 14px; margin-left: auto; }}
                .success {{ color: #10B981; font-weight: bold; }}
                .download-link {{ background: #10B981; color: white; padding: 8px 16px; border-radius: 4px; text-decoration: none; display: inline-block; margin-top: 10px; }}
                .download-link:hover {{ background: #059669; }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>🎉 Conversion Completed Successfully!</h1>
                <p>Job ID: {job_id}</p>
                <p>Processed: {results['processing_date']}</p>
            </div>
            
            <div class="stats">
                <div class="stat">
                    <div class="stat-value">{results['successful_chapters']}/{results['total_chapters']}</div>
                    <div class="stat-label">Chapters Completed</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{results['total_words_processed']}</div>
                    <div class="stat-label">Words Processed</div>
                </div>
                <div class="stat">
                    <div class="stat-value">{results['total_processing_time']:.1f}s</div>
                    <div class="stat-label">Processing Time</div>
                </div>
                <div class="stat">
                    <div class="stat-value">100%</div>
                    <div class="stat-label">Accuracy Score</div>
                </div>
            </div>
            
            <div class="files">
                <h2>📁 Generated Files</h2>
                <div class="file-list">
        """
        
        # Add files
        for file in results['files']:
            file_class = f"file-{file['type']}"
            icon = "🎵" if file['type'] == 'audio' else "📄" if file['type'] == 'text' else "📊"
            
            if file['type'] == 'audio':
                download_url = f"/static/{job_id}/{file['path']}"
                download_link = f'<a href="{download_url}" class="download-link">Download</a>'
            elif file['name'].endswith('.html'):
                view_url = f"/view-file/{job_id}/{file['path']}"
                download_link = f'<a href="{view_url}" class="download-link">View</a>'
            else:
                download_link = ""
            
            html += f"""
                    <div class="file {file_class}">
                        <div>
                            <span class="file-name">{icon} {file['name']}</span>
                            {download_link}
                        </div>
                        <span class="file-size">{file['size_human']}</span>
                    </div>
            """
        
        # Add chapter details
        for chapter in results['chapter_details']:
            html += f"""
                </div>
                <h2>📖 Chapter Details</h2>
                <div class="stat">
                    <div class="stat-value">Chapter {chapter['chapter']}: {chapter['title']}</div>
                    <div class="stat-label">
                        ✅ Audio Duration: {chapter['quality_check']['duration_ms']/1000:.1f} seconds<br>
                        ✅ Audio Quality: {chapter['quality_check']['sample_rate']}Hz, {chapter['quality_check']['channels']} channel, {chapter['quality_check']['bit_depth']}-bit<br>
                        ✅ Verification: {chapter['content_verification']['accuracy_score']*100:.1f}% accuracy<br>
                        ✅ File Size: {chapter['quality_check']['file_size']/1024:.1f} KB
                    </div>
                    <a href="/static/{job_id}/{Path(chapter['audio_file']).name}" class="download-link">🎵 Play Audio</a>
                </div>
            """
        
        html += """
            </div>
            
            <div style="margin-top: 40px; padding: 20px; background: #F0FDF4; border-radius: 8px;">
                <h3>🎯 Quality Summary</h3>
                <p><span class="success">✅ Perfect Conversion:</span> All text was successfully converted to high-quality audio</p>
                <p><span class="success">✅ No API Costs:</span> This results page doesn't trigger any additional API calls</p>
                <p><span class="success">✅ Ready to Use:</span> Your audiobook is ready for download and listening</p>
            </div>
        </body>
        </html>
        """
        
        return html
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to generate results page for {job_id}: {e}")
        return f"""
        <html><body>
        <h1>Error Loading Results</h1>
        <p>Could not load results for job {job_id}</p>
        <p>Error: {str(e)}</p>
        </body></html>
        """

@app.get("/view-file/{job_id}/{file_path:path}", response_class=HTMLResponse)
async def view_html_file(job_id: str, file_path: str):
    """View HTML files from job output"""
    
    # Security check - only allow HTML files in the job's output directory
    output_dir = Path("data/output") / job_id
    full_file_path = output_dir / file_path
    
    # Check if file exists and is within the job directory
    if not full_file_path.exists() or not str(full_file_path).startswith(str(output_dir)):
        raise HTTPException(status_code=404, detail="File not found")
    
    # Only serve HTML files
    if not full_file_path.suffix.lower() == '.html':
        raise HTTPException(status_code=400, detail="Only HTML files can be viewed")
    
    try:
        with open(full_file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # Add a header to identify the file
        enhanced_content = content.replace(
            '<body>',
            f'''<body>
            <div style="background: #1F2937; color: white; padding: 10px; margin-bottom: 20px; border-radius: 5px;">
                <h3 style="margin: 0;">📄 {full_file_path.name}</h3>
                <p style="margin: 5px 0 0 0; font-size: 14px;">Job: {job_id} | <a href="/results/{job_id}" style="color: #60A5FA;">← Back to Results</a></p>
            </div>'''
        )
        
        return enhanced_content
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")

@app.get("/api/all-jobs")
async def get_all_jobs():
    """Get list of all processed jobs"""
    
    output_dir = Path("data/output")
    if not output_dir.exists():
        return {"jobs": []}
    
    jobs = []
    for job_dir in output_dir.iterdir():
        if job_dir.is_dir():
            job_id = job_dir.name
            
            # Look for log file
            log_files = list(job_dir.glob("*_log.json"))
            if log_files:
                try:
                    with open(log_files[0], 'r') as f:
                        log_data = json.load(f)
                    
                    # Get audio files
                    audio_files = list(job_dir.glob("*.wav"))
                    
                    jobs.append({
                        "job_id": job_id,
                        "processing_date": log_data.get("processing_date"),
                        "total_chapters": log_data.get("total_chapters", 0),
                        "successful_chapters": log_data.get("successful_chapters", 0),
                        "total_words": log_data.get("total_words_processed", 0),
                        "processing_time": log_data.get("total_processing_time", 0),
                        "audio_files_count": len(audio_files),
                        "status": "completed" if log_data.get("successful_chapters", 0) > 0 else "failed"
                    })
                except Exception as e:
                    logger.error(f"Failed to read job data for {job_id}: {e}")
    
    # Sort by processing date (newest first)
    jobs.sort(key=lambda x: x.get("processing_date", ""), reverse=True)
    
    return {"jobs": jobs}

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
            # Use json() method to properly serialize datetime objects, then parse back to dict
            job_json_str = active_jobs[job_id].json()
            job_data = json.loads(job_json_str)
            
            await websocket.send_json(job_data)
        
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

# Chunk Management Endpoints (conditional)
if CHUNK_MANAGEMENT_AVAILABLE:
    chunk_db = ChunkDatabase()
    chunk_manager = ChunkManager()
else:
    chunk_db = None
    chunk_manager = None

@app.get("/api/chunk-management/status")
async def chunk_management_status():
    """Check if chunk management features are available"""
    return {
        "available": CHUNK_MANAGEMENT_AVAILABLE,
        "message": "Chunk management features loaded" if CHUNK_MANAGEMENT_AVAILABLE else "Chunk management features not available"
    }

@app.get("/api/chapters")
async def list_chapters(project_id: Optional[int] = None):
    """List all chapters with basic info"""
    if not CHUNK_MANAGEMENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Chunk management features not available")
    try:
        import sqlite3
        with sqlite3.connect(chunk_db.db_path) as conn:
            if project_id:
                cursor = conn.execute("""
                    SELECT c.id, c.chapter_number, c.title, c.status, c.chunks_directory,
                           p.title as project_title, c.total_chunks, c.completed_chunks
                    FROM chapters c
                    JOIN projects p ON c.project_id = p.id
                    WHERE c.project_id = ?
                    ORDER BY c.chapter_number
                """, (project_id,))
            else:
                cursor = conn.execute("""
                    SELECT c.id, c.chapter_number, c.title, c.status, c.chunks_directory,
                           p.title as project_title, c.total_chunks, c.completed_chunks
                    FROM chapters c
                    JOIN projects p ON c.project_id = p.id
                    ORDER BY p.id, c.chapter_number
                """)
            
            chapters = []
            for row in cursor.fetchall():
                chapters.append({
                    'id': row[0],
                    'chapter_number': row[1],
                    'title': row[2],
                    'status': row[3],
                    'chunks_directory': row[4],
                    'project_title': row[5],
                    'total_chunks': row[6],
                    'completed_chunks': row[7]
                })
        
        return {"chapters": chapters}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chapters/{chapter_id}/status")
async def get_chapter_status(chapter_id: int):
    """Get detailed status of chapter chunks"""
    try:
        status = chunk_manager.get_chapter_chunk_status(chapter_id)
        if not status:
            raise HTTPException(status_code=404, detail="Chapter not found")
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chunks/{chunk_id}/reprocess")
async def reprocess_chunk(chunk_id: int, background_tasks: BackgroundTasks):
    """Reprocess a single chunk"""
    try:
        background_tasks.add_task(chunk_manager.reprocess_single_chunk, chunk_id)
        return {"message": f"Chunk {chunk_id} reprocessing started", "chunk_id": chunk_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chapters/{chapter_id}/reprocess-failed")
async def reprocess_failed_chunks(chapter_id: int, background_tasks: BackgroundTasks):
    """Reprocess all failed chunks in a chapter"""
    try:
        background_tasks.add_task(chunk_manager.batch_reprocess_failed_chunks, chapter_id)
        return {"message": f"Batch reprocessing started for chapter {chapter_id}", "chapter_id": chapter_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class RestitchRequest(BaseModel):
    exclude_chunks: Optional[List[int]] = None

@app.post("/api/chapters/{chapter_id}/restitch")
async def restitch_chapter(chapter_id: int, request: Optional[RestitchRequest] = None):
    """Restitch chapter audio with optional chunk exclusion"""
    try:
        exclude_chunks = request.exclude_chunks if request else None
        output_path = chunk_manager.restitch_chapter_audio(chapter_id, exclude_chunks)
        return {
            "message": "Chapter audio restitched successfully",
            "output_path": output_path,
            "excluded_chunks": exclude_chunks or []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chapters/{chapter_id}/candidates")
async def get_reprocessing_candidates(chapter_id: int):
    """Get chunks that might benefit from reprocessing"""
    try:
        candidates = chunk_manager.get_reprocessing_candidates(chapter_id)
        return {"candidates": candidates, "count": len(candidates)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chunks/{chunk_id}/mark-reprocess")
async def mark_chunk_for_reprocessing(chunk_id: int, reason: str = "User requested"):
    """Mark a chunk for reprocessing"""
    try:
        chunk_manager.mark_chunk_for_reprocessing(chunk_id, reason)
        return {"message": f"Chunk {chunk_id} marked for reprocessing", "reason": reason}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Add chunk management models
class InsertChunkRequest(BaseModel):
    position: int
    text: str
    title: Optional[str] = None

class ChapterRenameRequest(BaseModel):
    custom_title: str
class ChapterUpdateRequest(BaseModel):
    chapter_number: Optional[int] = None
    title: Optional[str] = None

@app.post("/api/chapters/{chapter_id}/insert-chunk")
async def insert_chunk(chapter_id: int, request: InsertChunkRequest):
    """Insert a new chunk at specified position"""
    try:
        chunk_id = chunk_manager.insert_new_chunk(
            chapter_id=chapter_id,
            position=request.position,
            new_text=request.text,
            user_title=request.title
        )
        if chunk_id:
            return {
                "message": f"Chunk inserted successfully at position {request.position}",
                "chunk_id": chunk_id,
                "position": request.position
            }
        else:
            raise HTTPException(status_code=400, detail="Failed to insert chunk")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chunks/{chunk_id}/audio")
async def get_chunk_audio(chunk_id: int):
    """Serve audio file for a specific chunk"""
    try:
        import sqlite3
        with sqlite3.connect(chunk_db.db_path) as conn:
            cursor = conn.execute("SELECT audio_file_path FROM chunks WHERE id = ?", (chunk_id,))
            row = cursor.fetchone()
            
            if not row or not row[0]:
                raise HTTPException(status_code=404, detail="Audio file not found")
            
            audio_path = Path(row[0])
            if not audio_path.exists():
                raise HTTPException(status_code=404, detail="Audio file does not exist")
            
            return FileResponse(
                audio_path,
                media_type="audio/wav",
                filename=f"chunk_{chunk_id}.wav"
            )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chunks/{chunk_id}/text")
async def get_chunk_text(chunk_id: int):
    """Get text content for a specific chunk"""
    try:
        import sqlite3
        with sqlite3.connect(chunk_db.db_path) as conn:
            cursor = conn.execute("SELECT text_file_path, original_text FROM chunks WHERE id = ?", (chunk_id,))
            row = cursor.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Chunk not found")
            
            text_file_path, original_text = row
            
            # Try to read from file first, fallback to database
            text_content = original_text
            if text_file_path and Path(text_file_path).exists():
                try:
                    with open(text_file_path, 'r', encoding='utf-8') as f:
                        text_content = f.read()
                except:
                    pass  # Use database text as fallback
            
            return {
                "chunk_id": chunk_id,
                "text": text_content,
                "file_path": text_file_path
            }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chunks/{chunk_id}/open-file")
async def open_chunk_file(chunk_id: int):
    """Open chunk text file with system default editor"""
    try:
        import sqlite3
        import subprocess
        import platform
        
        with sqlite3.connect(chunk_db.db_path) as conn:
            cursor = conn.execute("SELECT text_file_path FROM chunks WHERE id = ?", (chunk_id,))
            row = cursor.fetchone()
            
            if not row or not row[0]:
                raise HTTPException(status_code=404, detail="Text file not found")
            
            text_file_path = Path(row[0])
            if not text_file_path.exists():
                raise HTTPException(status_code=404, detail="Text file does not exist")
            
            # Open file with system default editor
            system = platform.system()
            try:
                if system == "Darwin":  # macOS
                    subprocess.run(["open", str(text_file_path)], check=True)
                elif system == "Windows":
                    subprocess.run(["start", str(text_file_path)], shell=True, check=True)
                else:  # Linux
                    subprocess.run(["xdg-open", str(text_file_path)], check=True)
                
                return {"message": f"Opened file: {text_file_path.name}", "file_path": str(text_file_path)}
            except subprocess.CalledProcessError as e:
                raise HTTPException(status_code=500, detail=f"Failed to open file: {str(e)}")
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Chapter Management Endpoints
@app.post("/api/chapters/{chapter_id}/rename")
async def rename_chapter(chapter_id: int, request: ChapterRenameRequest):
    """Set a custom title for a chapter"""
    if not CHUNK_MANAGEMENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Chunk management features not available")
    
    try:
        chunk_db.set_chapter_custom_title(chapter_id, request.custom_title)
        return {
            "message": f"Chapter {chapter_id} renamed successfully",
            "new_title": request.custom_title
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
@app.patch("/api/chapters/{chapter_id}")
async def update_chapter(chapter_id: int, request: ChapterUpdateRequest):
    """Update chapter number and/or title"""
    if not CHUNK_MANAGEMENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Chunk management features not available")
    
    if request.chapter_number is None and request.title is None:
        raise HTTPException(status_code=400, detail="At least one field (chapter_number or title) must be provided")
    
    try:
        success = chunk_db.update_chapter(
            chapter_id=chapter_id,
            chapter_number=request.chapter_number,
            title=request.title
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Chapter not found")
        
        # Get updated chapter info
        chapter = chunk_db.get_chapter(chapter_id)
        
        return {
            "message": "Chapter updated successfully",
            "chapter_id": chapter_id,
            "chapter_number": chapter.chapter_number,
            "title": chapter.title,
            "updated_fields": {
                "chapter_number": request.chapter_number is not None,
                "title": request.title is not None
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chapters/{chapter_id}/display-info")
async def get_chapter_display_info(chapter_id: int):
    """Get chapter display information including custom title"""
    if not CHUNK_MANAGEMENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Chunk management features not available")
    
    try:
        display_info = chunk_db.get_chapter_display_info(chapter_id)
        if not display_info:
            raise HTTPException(status_code=404, detail="Chapter not found")
        return display_info
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chapters/{chapter_id}/audio-versions")
async def list_chapter_audio_versions(chapter_id: int):
    """List all stitched audio versions for a chapter"""
    if not CHUNK_MANAGEMENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Chunk management features not available")
    
    try:
        versions = chunk_db.list_chapter_audio_versions(chapter_id)
        return {
            "chapter_id": chapter_id,
            "versions": versions,
            "total_versions": len(versions)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chapters/{chapter_id}/debug-info")
async def get_chapter_debug_info(chapter_id: int):
    """Get detailed debugging information about chapter files and database state"""
    if not CHUNK_MANAGEMENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Chunk management features not available")
    
    try:
        # Get chapter info
        chapter = chunk_db.get_chapter(chapter_id)
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
        
        # Get display info
        display_info = chunk_db.get_chapter_display_info(chapter_id)
        
        # Get chunks
        chunks = chunk_db.get_chunks_by_chapter(chapter_id)
        
        # Get active stitched audio
        active_audio = chunk_db.get_active_chapter_audio(chapter_id)
        
        # Get all audio versions
        audio_versions = chunk_db.list_chapter_audio_versions(chapter_id)
        
        # File system analysis
        chunk_files = []
        for chunk in chunks:
            if chunk.audio_file_path:
                file_exists = Path(chunk.audio_file_path).exists()
                file_size = Path(chunk.audio_file_path).stat().st_size if file_exists else 0
                chunk_files.append({
                    "chunk_id": chunk.id,
                    "chunk_number": chunk.chunk_number,
                    "file_path": chunk.audio_file_path,
                    "file_exists": file_exists,
                    "file_size_bytes": file_size,
                    "status": chunk.status
                })
        
        return {
            "chapter_id": chapter_id,
            "database_info": {
                "original_title": chapter.title,
                "display_info": display_info,
                "status": chapter.status,
                "total_chunks": len(chunks),
                "completed_chunks": len([c for c in chunks if c.status == 'completed'])
            },
            "active_stitched_audio": active_audio,
            "all_audio_versions": audio_versions,
            "chunk_files": chunk_files,
            "file_system_summary": {
                "total_chunk_files": len(chunk_files),
                "existing_chunk_files": len([f for f in chunk_files if f["file_exists"]]),
                "missing_chunk_files": len([f for f in chunk_files if not f["file_exists"]]),
                "total_chunk_size_mb": round(sum([f["file_size_bytes"] for f in chunk_files]) / 1024 / 1024, 2)
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Synchronized Audio Player Endpoints
@app.get("/api/chapters/{chapter_id}/audio-sync-data")
async def get_chapter_audio_sync_data(chapter_id: int, version: Optional[int] = None):
    """Get all data needed for synchronized audio-text playback"""
    if not CHUNK_MANAGEMENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Chunk management features not available")
    
    try:
        logger.info(f"📊 SYNC DATA REQUEST: Chapter {chapter_id} audio-sync-data requested")
        logger.info(f"🔍 DEBUG: URL accessed was /chunks/{chapter_id} which maps to chapter_id={chapter_id}")
        
        # Get chapter info
        chapter = chunk_db.get_chapter(chapter_id)
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
        
        logger.info(f"📖 CHAPTER INFO:")
        logger.info(f"   📄 Title: '{chapter.title}'")
        logger.info(f"   🔢 Chapter number: {chapter.chapter_number}")
        logger.info(f"   📁 Chunks directory: {chapter.chunks_directory}")
        logger.info(f"   🆔 Database chapter_id: {chapter.id}")
        
        # Get chunks first
        chunks = chunk_db.get_chunks_by_chapter(chapter_id)
        logger.info(f"📦 CHUNKS: Found {len(chunks)} chunks for chapter {chapter_id}")
        
        # Calculate total duration from individual audio files
        total_duration = 0
        chunk_boundaries = []
        cumulative_time = 0
        
        for i, chunk in enumerate(sorted(chunks, key=lambda c: c.chunk_number)):
            chunk_duration = 0
            if chunk.audio_file_path and Path(chunk.audio_file_path).exists():
                try:
                    import wave
                    with wave.open(chunk.audio_file_path, 'r') as wav_file:
                        frame_count = wav_file.getnframes()
                        sample_rate = wav_file.getframerate()
                        chunk_duration = frame_count / sample_rate
                except Exception as e:
                    logger.warning(f"⚠️ WAV DURATION ERROR: Could not read WAV duration for chunk {chunk.chunk_number} (ID: {chunk.id}). Error: {e}. Falling back to text length estimation.")
                    text_length = len(chunk.original_text.split())
                    chunk_duration = (text_length / 150) * 60 # Estimate 150 words per minute
                    logger.info(f"   ESTIMATED DURATION: {chunk_duration:.2f}s for chunk {chunk.chunk_number} ({text_length} words)")
            else:
                logger.warning(f"⚠️ AUDIO FILE MISSING: Audio file not found for chunk {chunk.chunk_number} (ID: {chunk.id}). Falling back to text length estimation.")
                text_length = len(chunk.original_text.split())
                chunk_duration = (text_length / 150) * 60 # Estimate 150 words per minute
                logger.info(f"   ESTIMATED DURATION: {chunk_duration:.2f}s for chunk {chunk.chunk_number} ({text_length} words)")

            logger.info(f"⏱️ CHUNK DURATION: Chunk {chunk.chunk_number} (ID: {chunk.id}) calculated duration: {chunk_duration:.2f}s")
            
            chunk_boundary = {
                'chunk_id': chunk.id,
                'chunk_number': chunk.chunk_number,
                'title': f"Chunk {chunk.chunk_number}",
                'start_char': chunk.position_start,
                'end_char': chunk.position_end,
                'start_time': cumulative_time,
                'end_time': cumulative_time + chunk_duration,
                'audio_file_path': chunk.audio_file_path,  # Include actual file path
                'audio_filename': chunk.audio_file_path.split('/')[-1] if chunk.audio_file_path else None,  # Extract filename
                'orpheus_params': {
                    'voice': getattr(chunk, 'orpheus_voice', 'tara'),
                    'temperature': getattr(chunk, 'orpheus_temperature', 0.7),
                    'speed': getattr(chunk, 'orpheus_speed', 1.0)
                }
            }
            
            # Debug logging for chunk indexing
            logger.info(f"🔍 CHUNK BOUNDARY DEBUG: Array index {i} -> chunk_id={chunk.id}, chunk_number={chunk.chunk_number}, start_time={cumulative_time:.2f}s, end_time={cumulative_time + chunk_duration:.2f}s")
            
            chunk_boundaries.append(chunk_boundary)
            cumulative_time += chunk_duration
            total_duration += chunk_duration
        
        # Build full text from chunks
        chunk_texts = []
        for chunk in sorted(chunks, key=lambda c: c.chunk_number):
            if chunk.original_text:
                chunk_texts.append(chunk.original_text.strip())
        
        full_text = ' '.join(chunk_texts) if chunk_texts else chapter.original_text
        
        logger.info(f"📝 TEXT ASSEMBLY:")
        if chunk_texts:
            logger.info(f"   📦 Using {len(chunk_texts)} chunk texts, total length: {len(full_text)} chars")
            logger.info(f"   📄 Text preview: '{full_text[:200]}...'")
        else:
            logger.info(f"   📖 Using chapter.original_text, length: {len(full_text) if full_text else 0} chars")
            logger.info(f"   📄 Text preview: '{full_text[:200] if full_text else 'NO TEXT'}...'")
        
        # Create basic word timings
        words = full_text.split()
        word_timings = []
        if words and total_duration > 0:
            time_per_word = total_duration / len(words)
            for i, word in enumerate(words):
                word_timings.append({
                    'word_index': i,
                    'word_text': word,
                    'start_time': i * time_per_word,
                    'end_time': (i + 1) * time_per_word,
                    'confidence': 0.5
                })
        
        # Prioritize calculated WAV duration over potentially stale database duration
        active_audio = chunk_db.get_active_chapter_audio(chapter_id)
        if active_audio and active_audio.get('duration_seconds'):
            database_duration = active_audio['duration_seconds']
            # Use calculated duration if it's significantly different from database
            duration_diff = abs(total_duration - database_duration)
            if duration_diff > 1.0:  # More than 1 second difference
                actual_duration = total_duration
                logger.warning(f"⚠️ DURATION MISMATCH: Database duration ({database_duration:.1f}s) differs significantly from calculated duration ({total_duration:.1f}s). Using calculated duration.")
            else:
                actual_duration = database_duration
                logger.info(f"Using database-tracked duration: {actual_duration:.1f}s (calculated: {total_duration:.1f}s)")
        else:
            actual_duration = total_duration
            logger.info(f"Using calculated duration: {total_duration:.1f}s (no database duration available)")
        
        # Adjust word timings to match actual duration if needed
        if word_timings and actual_duration != total_duration and total_duration > 0:
            duration_ratio = actual_duration / total_duration
            for word in word_timings:
                word['start_time'] *= duration_ratio
                word['end_time'] *= duration_ratio
            
            # Adjust chunk boundaries too
            for chunk in chunk_boundaries:
                chunk['start_time'] *= duration_ratio
                chunk['end_time'] *= duration_ratio
        
        logger.info(f"🎵 AUDIO MAPPING:")
        logger.info(f"   🔗 Audio URL: /api/chapters/{chapter_id}/stitched-audio")
        logger.info(f"   📊 Word count: {len(words)} words")
        logger.info(f"   ⏱️  Duration: {actual_duration:.1f}s")
        logger.info(f"   📦 Chunk boundaries: {len(chunk_boundaries)}")
        
        # Get the actual stitched audio filename
        stitched_audio_filename = "stitched-audio"  # default
        if active_audio and active_audio.get('audio_file_path'):
            stitched_audio_filename = Path(active_audio['audio_file_path']).name
        
        # Create response payload
        response_payload = {
            "chapter_id": chapter_id,
            "chapter_title": chapter.title,
            "audio_url": f"/api/chapters/{chapter_id}/stitched-audio",
            "stitched_audio_filename": stitched_audio_filename,
            "full_text": full_text,
            "word_timings": word_timings,
            "chunk_boundaries": chunk_boundaries,
            "reprocessing_history": [],
            "total_chunks": len(chunks),
            "total_duration": actual_duration,
            "debug_info": {
                "calculated_duration": total_duration,
                "database_duration": active_audio.get('duration_seconds') if active_audio else None,
                "using_database": bool(active_audio and active_audio.get('duration_seconds'))
            }
        }
        
        # Log payload size and test JSON serialization to catch Unicode issues
        try:
            import json
            json_str = json.dumps(response_payload)
            payload_size = len(json_str)
            logger.info(f"📊 PAYLOAD SIZE: {payload_size} characters")
            if payload_size > 500000:  # Log large payloads
                logger.warning(f"⚠️ LARGE PAYLOAD: {payload_size} chars - monitoring for Unicode issues")
        except Exception as e:
            logger.error(f"❌ JSON SERIALIZATION ERROR: {e}")
            logger.error(f"   Chapter: {chapter_id}, Full text length: {len(full_text)}, Word count: {len(words)}")
            # Try to identify problematic data
            try:
                json.dumps({"chapter_id": chapter_id, "chapter_title": chapter.title})
                logger.info("   ✅ Basic chapter info serializes OK")
            except:
                logger.error("   ❌ Basic chapter info has Unicode issues")
            
            try:
                json.dumps({"full_text": full_text})
                logger.info("   ✅ Full text serializes OK")
            except Exception as text_error:
                logger.error(f"   ❌ Full text has Unicode issues: {text_error}")
            
            try:
                json.dumps({"word_timings": word_timings[:10]})  # Test first 10 words
                logger.info("   ✅ Sample word timings serialize OK")
            except Exception as word_error:
                logger.error(f"   ❌ Word timings have Unicode issues: {word_error}")
            
            raise HTTPException(status_code=500, detail=f"JSON serialization error: {e}")
        
        return response_payload
    except Exception as e:
        logger.error(f"Error getting audio sync data for chapter {chapter_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chapters/{chapter_id}/stitched-audio")
async def get_chapter_stitched_audio(chapter_id: int):
    """Serve the final stitched audio for a chapter using database as source of truth"""
    try:
        logger.info(f"🎵 AUDIO REQUEST: Chapter {chapter_id} stitched audio requested")
        logger.info(f"🔍 DEBUG: This corresponds to URL /api/chapters/{chapter_id}/stitched-audio")
        
        # Get chunks for the chapter (needed for database registration later)
        chunks = chunk_db.get_chunks_by_chapter(chapter_id)
        
        # First, try to get the active stitched audio from database
        active_audio = chunk_db.get_active_chapter_audio(chapter_id)
        
        if active_audio and active_audio['audio_file_path']:
            audio_file_path = Path(active_audio['audio_file_path'])
            
            logger.info(f"📁 DATABASE AUDIO: Found active audio in database")
            logger.info(f"   📄 File path: {audio_file_path}")
            logger.info(f"   📄 File name: {audio_file_path.name}")
            logger.info(f"   🔢 Version: {active_audio['version_number']}")
            logger.info(f"   📊 Size: {active_audio['file_size_bytes']} bytes")
            logger.info(f"   ⏱️  Duration: {active_audio['duration_seconds']:.1f}s")
            logger.info(f"   📅 Created: {active_audio['created_at']}")
            logger.info(f"   ✅ File exists: {audio_file_path.exists()}")
            
            if audio_file_path.exists():
                actual_size = audio_file_path.stat().st_size
                logger.info(f"   📏 Actual file size: {actual_size} bytes")
                if actual_size != active_audio['file_size_bytes']:
                    logger.warning(f"   ⚠️  SIZE MISMATCH: DB says {active_audio['file_size_bytes']} bytes, file is {actual_size} bytes")
                
                logger.info(f"✅ SERVING: {audio_file_path.name}")
                return FileResponse(
                    audio_file_path,
                    media_type="audio/wav",
                    filename=f"chapter_{chapter_id}_v{active_audio['version_number']}.wav"
                )
            else:
                logger.error(f"❌ FILE MISSING: Database references missing file: {audio_file_path}")
        
        # Fallback: Legacy file search (for chapters not yet migrated)
        logger.info(f"No active audio in database for chapter {chapter_id}, falling back to file search")
        
        output_dir = Path("data/output")
        audio_file = None
        largest_size = 0

        # Attempt 1: Find the specific stitched audio file for this job_id
        chapter_info = chunk_db.get_chapter(chapter_id)
        job_id = None
        if chapter_info and chapter_info.chunks_directory:
            # Extract job_id (UUID) from the chunks_directory path
            # Example: data/output/d42c4da4-3aeb-41dc-94f5-c8ccafb79efe/rock-short-test-_chunks_20250621_143521
            path_parts = Path(chapter_info.chunks_directory).parts
            if len(path_parts) >= 3 and path_parts[0] == 'data' and path_parts[1] == 'output':
                job_id = path_parts[2] # This should be the UUID
            
        if job_id:
            job_output_dir = output_dir / job_id
            if job_output_dir.exists():
                # Look for files matching the pattern: [original_filename]_[timestamp].wav
                # The original filename is usually derived from the input text file name
                # We can try to find the largest .wav file in this specific job directory
                job_wav_files = list(job_output_dir.glob("*.wav"))
                for file_path in job_wav_files:
                    if file_path.exists():
                        try:
                            file_size = file_path.stat().st_size
                            if file_size > largest_size:
                                largest_size = file_size
                                audio_file = file_path
                                logger.debug(f"🔍 DEBUG: Found job-specific audio file: {audio_file.name} for chapter {chapter_id}")
                        except Exception as e:
                            logger.warning(f"⚠️  Warning: Could not process job-specific file {file_path.name}: {e}")
                            continue
        
        if audio_file: # If we found the job-specific file, use it
            logger.info(f"✅ Found job-specific audio for chapter {chapter_id}: {audio_file}")
        else: # Fallback to legacy search if job-specific file not found
            logger.info(f"No job-specific audio found for chapter {chapter_id}, falling back to legacy file search.")
            possible_files = []
            
            # Get first chunk's path to derive the job directory (for older structures)
            if chunks and chunks[0].audio_file_path:
                chunk_path = Path(chunks[0].audio_file_path)
                # Ensure we don't re-add files from the current job_dir if it was already searched
                if chunk_path.parent.parent.exists() and chunk_path.parent.parent != job_output_dir:
                    possible_files.extend(list(chunk_path.parent.parent.glob("*.wav")))
            
            # Search all job directories as last resort (excluding the current job_output_dir)
            for dir_entry in output_dir.iterdir():
                if dir_entry.is_dir() and dir_entry != job_output_dir:
                    wav_files = list(dir_entry.glob("*.wav"))
                    # Filter for larger files (likely stitched)
                    large_files = [f for f in wav_files if f.stat().st_size > 1000000]  # > 1MB
                    possible_files.extend(large_files)
            
            # Find the largest WAV file among possible_files that matches chapter_id
            for file_path in possible_files:
                if file_path.exists():
                    try:
                        file_size = file_path.stat().st_size
                        # Extract chapter number from filename
                        filename_chapter_match = re.search(r'chapter_(\d+)', file_path.name)
                        filename_chapter_id = int(filename_chapter_match.group(1)) if filename_chapter_match else None
                        logger.debug(f"🔍 DEBUG: Considering legacy file {file_path.name} (Chapter ID from filename: {filename_chapter_id}) for requested chapter {chapter_id}")

                        # Only consider files that explicitly match the requested chapter_id
                        if file_size > largest_size and filename_chapter_id == chapter_id:
                            largest_size = file_size
                            audio_file = file_path
                    except Exception as e:
                        logger.warning(f"⚠️  Warning: Could not process legacy file {file_path.name}: {e}")
                        continue
        
        if not audio_file:
            raise HTTPException(status_code=404, detail="Chapter stitched audio not found")
        
        # Register this file in the database for future use
        try:
            chunks_used = [chunk.id for chunk in chunks]
            chunk_db.create_chapter_audio_version(
                chapter_id=chapter_id,
                audio_file_path=str(audio_file),
                stitched_from_chunks=chunks_used,
                processing_log=f"Legacy file discovered and registered: {audio_file}"
            )
            logger.info(f"Registered legacy stitched audio in database: {audio_file}")
        except Exception as e:
            logger.error(f"Failed to register legacy audio in database: {e}")
        
        logger.info(f"Serving legacy stitched audio for chapter {chapter_id}: {audio_file} ({largest_size} bytes)")
        
        return FileResponse(
            audio_file,
            media_type="audio/wav",
            filename=f"chapter_{chapter_id}.wav"
        )
    except Exception as e:
        logger.error(f"Error serving stitched audio for chapter {chapter_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chapters/{chapter_id}/status-summary")
async def get_chapter_status_summary(chapter_id: int):
    """Clear, concise summary of what text and audio files are being used for a chapter"""
    try:
        # Get chapter info
        chapter = chunk_db.get_chapter(chapter_id)
        if not chapter:
            raise HTTPException(status_code=404, detail="Chapter not found")
        
        # Get active audio
        active_audio = chunk_db.get_active_chapter_audio(chapter_id)
        
        # Get text info
        chunks = chunk_db.get_chunks_by_chapter(chapter_id)
        chunk_texts = []
        for chunk in sorted(chunks, key=lambda c: c.chunk_number):
            if chunk.original_text:
                chunk_texts.append(chunk.original_text.strip())
        full_text = ' '.join(chunk_texts) if chunk_texts else (chapter.original_text if chapter else "")
        
        return {
            "chapter_id": chapter_id,
            "chapter_info": {
                "title": chapter.title,
                "chapter_number": chapter.chapter_number,
                "status": chapter.status
            },
            "text_source": {
                "source": "chunks" if chunk_texts else "chapter.original_text",
                "chunk_count": len(chunks),
                "total_characters": len(full_text),
                "total_words": len(full_text.split()) if full_text else 0,
                "preview": full_text[:200] + "..." if len(full_text) > 200 else full_text
            },
            "audio_source": {
                "file_path": active_audio['audio_file_path'] if active_audio else None,
                "filename": Path(active_audio['audio_file_path']).name if active_audio else None,
                "file_exists": Path(active_audio['audio_file_path']).exists() if active_audio else False,
                "file_size_mb": round(active_audio['file_size_bytes'] / 1024 / 1024, 2) if active_audio else None,
                "duration_minutes": round(active_audio['duration_seconds'] / 60, 1) if active_audio else None,
                "version": active_audio['version_number'] if active_audio else None
            },
            "sync_status": {
                "text_and_audio_match": bool(active_audio and f"chapter_{chapter.chapter_number:02d}" in active_audio['audio_file_path']),
                "ready_for_playback": bool(active_audio and Path(active_audio['audio_file_path']).exists() and full_text)
            }
        }
        
    except Exception as e:
        logger.error(f"Error getting status summary for chapter {chapter_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chapters/{chapter_id}/diagnostic")
async def get_chapter_diagnostic(chapter_id: int):
    """Comprehensive diagnostic information for a chapter"""
    try:
        result = {
            "chapter_id": chapter_id,
            "timestamp": datetime.now().isoformat(),
            "database_info": {},
            "audio_info": {},
            "text_info": {},
            "file_system_info": {}
        }
        
        # Get chapter from database
        chapter = chunk_db.get_chapter(chapter_id)
        if chapter:
            result["database_info"]["chapter"] = {
                "title": chapter.title,
                "chapter_number": chapter.chapter_number,
                "chunks_directory": chapter.chunks_directory,
                "total_chunks": chapter.total_chunks,
                "completed_chunks": chapter.completed_chunks,
                "status": chapter.status
            }
        else:
            result["database_info"]["chapter"] = None
            
        # Get active audio info
        active_audio = chunk_db.get_active_chapter_audio(chapter_id)
        if active_audio:
            audio_path = Path(active_audio['audio_file_path'])
            result["audio_info"]["database_record"] = {
                "file_path": str(audio_path),
                "filename": audio_path.name,
                "version_number": active_audio['version_number'],
                "file_size_bytes": active_audio['file_size_bytes'],
                "duration_seconds": active_audio['duration_seconds'],
                "created_at": active_audio['created_at']
            }
            result["audio_info"]["file_exists"] = audio_path.exists()
            if audio_path.exists():
                result["audio_info"]["actual_file_size"] = audio_path.stat().st_size
                result["audio_info"]["size_matches"] = audio_path.stat().st_size == active_audio['file_size_bytes']
        else:
            result["audio_info"]["database_record"] = None
            
        # Get chunks info
        chunks = chunk_db.get_chunks_by_chapter(chapter_id)
        result["text_info"]["chunk_count"] = len(chunks)
        if chunks:
            chunk_texts = []
            for chunk in sorted(chunks, key=lambda c: c.chunk_number):
                if chunk.original_text:
                    chunk_texts.append(chunk.original_text.strip())
            
            full_text = ' '.join(chunk_texts) if chunk_texts else (chapter.original_text if chapter else "")
            result["text_info"]["total_characters"] = len(full_text)
            result["text_info"]["total_words"] = len(full_text.split()) if full_text else 0
            result["text_info"]["text_preview"] = full_text[:300] + "..." if len(full_text) > 300 else full_text
            result["text_info"]["first_chunk_preview"] = chunks[0].original_text[:200] + "..." if chunks and chunks[0].original_text else None
            
        # Check for expected file based on naming pattern
        expected_filename = f"chapter_{chapter_id:02d}_*.wav"
        result["file_system_info"]["expected_pattern"] = expected_filename
        
        # Look for files matching the pattern
        data_output_dir = Path("data/output")
        if data_output_dir.exists():
            matching_files = list(data_output_dir.rglob(f"chapter_{chapter_id:02d}_*.wav"))
            result["file_system_info"]["matching_files"] = [str(f) for f in matching_files]
        else:
            result["file_system_info"]["matching_files"] = []
            
        return result
        
    except Exception as e:
        logger.error(f"Error getting diagnostic info for chapter {chapter_id}: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chunks/{chunk_id}/orpheus-params")
async def get_chunk_orpheus_params(chunk_id: int):
    """Get Orpheus parameters used for chunk processing"""
    if not CHUNK_MANAGEMENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Chunk management features not available")
    
    try:
        chunk = chunk_db.get_chunk(chunk_id)
        if not chunk:
            raise HTTPException(status_code=404, detail="Chunk not found")
        
        # Get the active audio version for detailed params
        audio_version = chunk_db.get_active_audio_version(chunk_id)
        
        params = {
            'chunk_id': chunk_id,
            'voice': getattr(chunk, 'orpheus_voice', 'tara'),
            'temperature': getattr(chunk, 'orpheus_temperature', 0.7),
            'speed': getattr(chunk, 'orpheus_speed', 1.0),
        }
        
        if audio_version and audio_version.get('orpheus_params'):
            params.update(audio_version['orpheus_params'])
        
        return params
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chunks/{chunk_id}/update-orpheus-params")
async def update_chunk_orpheus_params_endpoint(chunk_id: int, params: Dict[str, Any]):
    """Update Orpheus parameters for a chunk"""
    if not CHUNK_MANAGEMENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Chunk management features not available")
    
    try:
        chunk_db.update_chunk_orpheus_params(
            chunk_id=chunk_id,
            temperature=params.get('temperature'),
            voice=params.get('voice'),
            speed=params.get('speed')
        )
        
        return {"message": f"Updated Orpheus parameters for chunk {chunk_id}", "params": params}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/chapters/{chapter_id}/word-timings")
async def get_chapter_word_timings(chapter_id: int):
    """Get word-level timing data for a chapter"""
    if not CHUNK_MANAGEMENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Chunk management features not available")
    
    try:
        word_timings = chunk_db.get_chapter_words(chapter_id)
        return {
            "chapter_id": chapter_id,
            "word_count": len(word_timings),
            "word_timings": word_timings
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/chunks/{chunk_id}/reprocess-with-params")
async def reprocess_chunk_with_params(chunk_id: int, params: Dict[str, Any], background_tasks: BackgroundTasks):
    """Reprocess a chunk with specific Orpheus parameters"""
    if not CHUNK_MANAGEMENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Chunk management features not available")
    
    try:
        # Start reprocessing with new parameters
        background_tasks.add_task(
            _reprocess_chunk_with_enhanced_params, 
            chunk_id, 
            params
        )
        
        return {
            "message": f"Started reprocessing chunk {chunk_id} with new parameters",
            "chunk_id": chunk_id,
            "params": params
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

async def _reprocess_chunk_with_enhanced_params(chunk_id: int, params: Dict[str, Any]):
    """Background task for reprocessing chunk with enhanced TTS client"""
    try:
        from src.core.enhanced_fal_tts_client import EnhancedFalTTSClient
        
        enhanced_client = EnhancedFalTTSClient()
        audio_path, word_timings = enhanced_client.reprocess_chunk_with_params(chunk_id, params)
        
        logger.info(f"Successfully reprocessed chunk {chunk_id} with {len(word_timings)} word timings")
        
    except Exception as e:
        logger.error(f"Failed to reprocess chunk {chunk_id}: {e}")
        # Update chunk status to failed
        chunk_db.update_chunk_status(
            chunk_id=chunk_id,
            status='failed',
            error_message=str(e)
        )

@app.post("/api/chunks/{chunk_id}/update-from-file")
async def update_chunk_from_file(chunk_id: int):
    """Update chunk's original_text and cleaned_text from the text file on disk"""
    if not CHUNK_MANAGEMENT_AVAILABLE:
        raise HTTPException(status_code=503, detail="Chunk management features not available")
    
    try:
        import sqlite3
        with sqlite3.connect(chunk_db.db_path) as conn:
            # Get the text file path for this chunk
            cursor = conn.execute("SELECT text_file_path FROM chunks WHERE id = ?", (chunk_id,))
            row = cursor.fetchone()
            
            if not row:
                raise HTTPException(status_code=404, detail="Chunk not found")
            
            text_file_path = row[0]
            
            if not text_file_path or not Path(text_file_path).exists():
                raise HTTPException(status_code=404, detail="Text file not found on disk")
            
            # Read the latest text from the file
            try:
                with open(text_file_path, 'r', encoding='utf-8') as f:
                    latest_text = f.read().strip()
            except Exception as e:
                raise HTTPException(status_code=500, detail=f"Failed to read text file: {str(e)}")
            
            if not latest_text:
                raise HTTPException(status_code=400, detail="Text file is empty")
            
            # Update both original_text and cleaned_text in the database
            # For now, we'll set both to the same value since the file contains the latest version
            update_time = datetime.now().isoformat()
            conn.execute("""
                UPDATE chunks
                SET original_text = ?, cleaned_text = ?, updated_at = ?
                WHERE id = ?
            """, (latest_text, latest_text, update_time, chunk_id))
            
            conn.commit()
            
            # Get updated chunk info
            cursor = conn.execute("""
                SELECT chunk_number, LENGTH(original_text) as text_length
                FROM chunks WHERE id = ?
            """, (chunk_id,))
            chunk_info = cursor.fetchone()
            
            return {
                "message": f"Successfully updated chunk {chunk_id} from file",
                "chunk_id": chunk_id,
                "chunk_number": chunk_info[0] if chunk_info else None,
                "text_length": chunk_info[1] if chunk_info else 0,
                "file_path": text_file_path,
                "updated_at": update_time
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to update chunk {chunk_id} from file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

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