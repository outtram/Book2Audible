#!/usr/bin/env python3
"""
Import legacy job data into chunk management database.
This allows retroactive chunk management on jobs processed before the chunk database existed.
"""

import sys
import json
import sqlite3
from pathlib import Path
from datetime import datetime

def import_legacy_job(job_id: str):
    """Import a legacy job into the chunk management database"""
    
    # Paths
    job_dir = Path(f"data/output/{job_id}")
    db_path = Path("data/chunk_database.db")
    
    if not job_dir.exists():
        print(f"❌ Job directory not found: {job_dir}")
        return False
    
    # Find log file
    log_files = list(job_dir.glob("*_log.json"))
    if not log_files:
        print(f"❌ No log file found in {job_dir}")
        return False
    
    log_file = log_files[0]
    print(f"📄 Found log file: {log_file}")
    
    # Read log data
    try:
        with open(log_file, 'r') as f:
            log_data = json.load(f)
    except Exception as e:
        print(f"❌ Failed to read log file: {e}")
        return False
    
    # Initialize database
    with sqlite3.connect(db_path) as conn:        
        # Check if job already exists
        cursor = conn.execute("""
            SELECT p.id FROM projects p 
            JOIN chapters c ON p.id = c.project_id 
            WHERE c.chunks_directory LIKE ?
        """, (f"%{job_id}%",))
        
        if cursor.fetchone():
            print(f"⚠️  Job {job_id} already exists in database")
            return False
        
        # Create project
        project_title = f"Legacy Import: {job_id}"
        original_file = log_data.get('input_file', f"legacy_job_{job_id}")
        created_at = log_data.get('processing_date', datetime.now().isoformat())
        
        cursor = conn.execute("""
            INSERT INTO projects (title, original_file, created_at, status, total_chapters, metadata) 
            VALUES (?, ?, ?, ?, ?, ?)
        """, (project_title, original_file, created_at, 'completed', log_data.get('total_chapters', 1), json.dumps({'legacy_import': True, 'job_id': job_id})))
        project_id = cursor.lastrowid
        
        print(f"✅ Created project {project_id}: {project_title}")
        
        # Import chapters
        chapters_imported = 0
        chunks_imported = 0
        
        for chapter_detail in log_data.get('chapter_details', []):
            chapter_number = chapter_detail.get('chapter', 1)
            chapter_title = chapter_detail.get('title', f"Chapter {chapter_number}")
            chunks_directory = chapter_detail.get('chunks_directory', '')
            chunk_count = chapter_detail.get('chunk_count', 0)
            
            # Create chapter - need to read original text from first chunk file
            original_text = ""
            first_chunk_file = Path(chunks_directory) / f"chapter_{chapter_number:02d}_chunk_001.txt"
            if not first_chunk_file.exists():
                # Try alternative naming pattern
                first_chunk_file = Path(chunks_directory) / f"chapter_03_chunk_001.txt"
            
            if first_chunk_file.exists():
                try:
                    with open(first_chunk_file, 'r') as f:
                        original_text = f.read()[:100] + "..."  # Sample for original_text
                except:
                    original_text = "Legacy imported chapter"
            else:
                original_text = "Legacy imported chapter"
            
            cursor = conn.execute("""
                INSERT INTO chapters (project_id, chapter_number, title, original_text, cleaned_text, chunks_directory, total_chunks, completed_chunks, status, created_at, updated_at, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (project_id, chapter_number, chapter_title, original_text, original_text, chunks_directory, chunk_count, chunk_count, 'completed', created_at, created_at, json.dumps({'legacy_import': True})))
            chapter_id = cursor.lastrowid
            
            print(f"  📖 Imported chapter {chapter_id}: {chapter_title} ({chunk_count} chunks)")
            chapters_imported += 1
            
            # Import chunks
            for chunk_result in chapter_detail.get('chunk_results', []):
                chunk_number = chunk_result.get('chunk_number')
                text_file = chunk_result.get('text_file', '')
                audio_file = chunk_result.get('audio_file', '')
                transcription_file = chunk_result.get('transcription_file', '')
                diff_file = chunk_result.get('diff_file', '')
                text_length = chunk_result.get('text_length', 0)
                word_count = chunk_result.get('word_count', 0)
                
                verification = chunk_result.get('verification', {})
                accuracy_score = verification.get('accuracy_score', 0.0)
                word_error_rate = verification.get('word_error_rate', 0.0)
                character_error_rate = verification.get('character_error_rate', 0.0)
                verification_passed = verification.get('is_verified', False)
                error_message = verification.get('error_message')
                
                # Determine status based on verification
                if verification_passed and accuracy_score > 0.9:
                    status = 'completed'
                elif verification_passed and accuracy_score > 0.7:
                    status = 'needs_attention'
                else:
                    status = 'failed'
                
                # Read chunk text for database
                chunk_text = ""
                if Path(text_file).exists():
                    try:
                        with open(text_file, 'r') as f:
                            chunk_text = f.read()
                    except:
                        chunk_text = f"Legacy chunk {chunk_number}"
                
                # Calculate positions (approximate)
                position_start = (chunk_number - 1) * 200  # Rough estimate
                position_end = position_start + text_length
                
                conn.execute("""
                    INSERT INTO chunks (
                        chapter_id, chunk_number, position_start, position_end, original_text, cleaned_text,
                        text_file_path, audio_file_path, transcription_file_path, diff_file_path,
                        status, verification_score, error_message, created_at, updated_at, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    chapter_id, chunk_number, position_start, position_end, chunk_text, chunk_text,
                    text_file, audio_file, transcription_file, diff_file,
                    status, accuracy_score, error_message, created_at, created_at, 
                    json.dumps({
                        'legacy_import': True,
                        'word_count': word_count,
                        'text_length': text_length,
                        'word_error_rate': word_error_rate,
                        'character_error_rate': character_error_rate,
                        'verification_passed': verification_passed
                    })
                ))
                
                chunks_imported += 1
            
        conn.commit()
        
        print(f"✅ Import completed!")
        print(f"   📊 Imported: {chapters_imported} chapters, {chunks_imported} chunks")
        print(f"   🎯 Project ID: {project_id}")
        print(f"   🔗 Access via: http://localhost:3000/chapters")
        
        return True

def main():
    if len(sys.argv) != 2:
        print("Usage: python import_legacy_job.py <job_id>")
        print("Example: python import_legacy_job.py 5f9149c7-1fca-4d3d-bbbe-1d0d43a8f6e2")
        return
    
    job_id = sys.argv[1]
    print(f"🔄 Importing legacy job: {job_id}")
    
    success = import_legacy_job(job_id)
    if success:
        print(f"\n🎉 Successfully imported job {job_id} into chunk management database!")
        print("You can now use the chunk management features:")
        print("- View chunks: python chunk_cli.py chapter-status <chapter_id>")
        print("- Reprocess chunks: python chunk_cli.py reprocess-chunk <chunk_id>")
        print("- Web interface: http://localhost:3000/chapters")
    else:
        print(f"❌ Failed to import job {job_id}")

if __name__ == "__main__":
    main()