#!/usr/bin/env python3
"""
Import the test chapter into the database to test our database tracking system
"""

import sys
from pathlib import Path
from datetime import datetime
import json

# Add src to path
sys.path.append(str(Path(__file__).parent / "src"))

from src.core.chunk_database import ChunkDatabase

def import_test_chapter():
    """Import the test chapter and its chunks into the database"""
    
    chunk_db = ChunkDatabase()
    
    # Chapter info
    chapter_title = "Database Testing"
    original_text_file = Path("data/input/test_db_chapter.txt")
    chunks_dir = Path("data/output/test_db_chapter_chunks_20250603_231310")
    stitched_audio = Path("data/output/test_db_chapter_20250603_231310.wav")
    
    # Read original text
    with open(original_text_file, 'r', encoding='utf-8') as f:
        original_text = f.read()
    
    print("🔄 Creating project and chapter...")
    
    # Create project
    project_id = chunk_db.create_project(
        title="Database Testing Project",
        original_file=str(original_text_file)
    )
    print(f"✅ Created project {project_id}")
    
    # Create chapter
    chapter_id = chunk_db.create_chapter(
        project_id=project_id,
        chapter_number=1,
        title=chapter_title,
        original_text=original_text,
        cleaned_text=original_text,
        chunks_directory=str(chunks_dir)
    )
    print(f"✅ Created chapter {chapter_id}")
    
    print("🔄 Adding chunks...")
    
    # Add chunks
    chunk_files = list(chunks_dir.glob("test_db_chapter_chunk_*.txt"))
    chunk_files.sort()
    
    chunk_ids = []
    for i, chunk_file in enumerate(chunk_files, 1):
        # Read chunk text
        with open(chunk_file, 'r', encoding='utf-8') as f:
            chunk_text = f.read()
        
        # Find corresponding audio file
        audio_file = chunk_file.with_suffix('.wav')
        
        chunk_id = chunk_db.create_chunk(
            chapter_id=chapter_id,
            chunk_number=i,
            position_start=0,  # Simplified for test
            position_end=len(chunk_text),
            original_text=chunk_text,
            cleaned_text=chunk_text,
            text_file_path=str(chunk_file)
        )
        
        # Update the chunk with audio file path and completed status
        if audio_file.exists():
            chunk_db.update_chunk_status(chunk_id, 'completed', str(audio_file))
        chunk_ids.append(chunk_id)
        print(f"✅ Added chunk {i} (ID: {chunk_id})")
    
    print("🔄 Registering stitched audio...")
    
    # Register stitched audio version
    if stitched_audio.exists():
        version_id = chunk_db.create_chapter_audio_version(
            chapter_id=chapter_id,
            audio_file_path=str(stitched_audio),
            stitched_from_chunks=chunk_ids,
            processing_log=f"Test chapter processed on {datetime.now().isoformat()}"
        )
        print(f"✅ Registered stitched audio version {version_id}")
    
    print("🔄 Setting custom title...")
    
    # Set custom title
    chunk_db.set_chapter_custom_title(chapter_id, "Test Chapter: Database Validation")
    print(f"✅ Set custom title")
    
    print(f"🎉 Test chapter imported successfully!")
    print(f"   Project ID: {project_id}")
    print(f"   Chapter ID: {chapter_id}")
    print(f"   Chunks: {len(chunk_ids)}")
    print(f"   Stitched Audio: {stitched_audio}")
    
    return chapter_id

if __name__ == "__main__":
    chapter_id = import_test_chapter()