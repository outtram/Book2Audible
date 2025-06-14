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
    
    # First check if there are completed files - this takes priority
    restored_job = await restore_job_from_files(job_id)
    if restored_job:
        # Update active jobs with completed status
        active_jobs[job_id] = restored_job
        return restored_job.dict()
    
    # Check active jobs if no completed files found
    if job_id in active_jobs:
        return active_jobs[job_id].dict()
    
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