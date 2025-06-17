#!/usr/bin/env python3
"""
Chapter 15 Cleanup Script
Fixes database inconsistencies after FAL credit exhaustion and regeneration
"""

import sqlite3
import os
import shutil
import glob
from datetime import datetime
import json

def backup_database():
    """Create a backup of the current database"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = f"data/chunk_database_backup_{timestamp}.db"
    shutil.copy2("data/chunk_database.db", backup_path)
    print(f"✅ Database backed up to: {backup_path}")
    return backup_path

def verify_audio_files(chunks_dir, chunk_numbers):
    """Verify that regenerated audio files exist and are valid"""
    verified_chunks = []
    for chunk_num in chunk_numbers:
        regenerated_file = f"{chunks_dir}/chapter_15_chunk_{chunk_num:03d}_REGENERATED.wav"
        if os.path.exists(regenerated_file) and os.path.getsize(regenerated_file) > 0:
            verified_chunks.append(chunk_num)
        else:
            print(f"⚠️  Warning: {regenerated_file} missing or empty")
    
    print(f"✅ Verified {len(verified_chunks)} regenerated audio files")
    return verified_chunks

def update_database(verified_chunks, chunks_dir):
    """Update database to reflect regenerated files"""
    conn = sqlite3.connect('data/chunk_database.db')
    cursor = conn.cursor()
    
    updated_count = 0
    
    for chunk_num in verified_chunks:
        # Update chunk status and audio file path
        regenerated_file = f"{chunks_dir}/chapter_15_chunk_{chunk_num:03d}_REGENERATED.wav"
        
        cursor.execute("""
            UPDATE chunks 
            SET status = 'completed',
                audio_file_path = ?,
                updated_at = ?,
                error_message = NULL
            WHERE chapter_id = 7 AND chunk_number = ?
        """, (regenerated_file, datetime.now().isoformat(), chunk_num))
        
        if cursor.rowcount > 0:
            updated_count += 1
            print(f"✅ Updated chunk {chunk_num}")
        else:
            print(f"⚠️  Warning: Could not update chunk {chunk_num}")
    
    # Update chapter metadata
    cursor.execute("""
        UPDATE chapters 
        SET completed_chunks = (
            SELECT COUNT(*) FROM chunks 
            WHERE chapter_id = 7 AND status = 'completed'
        ),
        total_chunks = (
            SELECT COUNT(*) FROM chunks 
            WHERE chapter_id = 7
        ),
        status = 'completed',
        updated_at = ?
        WHERE id = 7
    """, (datetime.now().isoformat(),))
    
    conn.commit()
    
    # Get final counts
    cursor.execute("SELECT total_chunks, completed_chunks FROM chapters WHERE id = 7")
    total, completed = cursor.fetchone()
    
    conn.close()
    
    print(f"✅ Updated {updated_count} chunks in database")
    print(f"✅ Chapter 15 status: {completed}/{total} chunks completed")
    
    return updated_count, total, completed

def rename_regenerated_files(chunks_dir, verified_chunks):
    """Rename REGENERATED files to standard naming convention"""
    renamed_count = 0
    
    for chunk_num in verified_chunks:
        regenerated_file = f"{chunks_dir}/chapter_15_chunk_{chunk_num:03d}_REGENERATED.wav"
        standard_file = f"{chunks_dir}/chapter_15_chunk_{chunk_num:03d}.wav"
        
        if os.path.exists(regenerated_file):
            # Remove existing standard file if it exists
            if os.path.exists(standard_file):
                os.remove(standard_file)
            
            # Rename regenerated file to standard name
            os.rename(regenerated_file, standard_file)
            renamed_count += 1
            print(f"✅ Renamed chunk {chunk_num} file")
    
    print(f"✅ Renamed {renamed_count} audio files")
    return renamed_count

def update_database_paths(chunks_dir, verified_chunks):
    """Update database paths to point to renamed files"""
    conn = sqlite3.connect('data/chunk_database.db')
    cursor = conn.cursor()
    
    for chunk_num in verified_chunks:
        standard_file = f"{chunks_dir}/chapter_15_chunk_{chunk_num:03d}.wav"
        
        cursor.execute("""
            UPDATE chunks 
            SET audio_file_path = ?,
                updated_at = ?
            WHERE chapter_id = 7 AND chunk_number = ?
        """, (standard_file, datetime.now().isoformat(), chunk_num))
    
    conn.commit()
    conn.close()
    
    print(f"✅ Updated database paths for {len(verified_chunks)} chunks")

def create_final_report(backup_path, total_chunks, completed_chunks, updated_count):
    """Create a final cleanup report"""
    report = {
        "cleanup_timestamp": datetime.now().isoformat(),
        "database_backup": backup_path,
        "chapter_id": 7,
        "chapter_number": 15,
        "title": "A Pathway Towards Wholeness",
        "total_chunks": total_chunks,
        "completed_chunks": completed_chunks,
        "chunks_updated": updated_count,
        "completion_percentage": (completed_chunks / total_chunks) * 100 if total_chunks > 0 else 0,
        "status": "SUCCESS" if completed_chunks == total_chunks else "PARTIAL"
    }
    
    report_path = f"chapter_15_cleanup_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(report_path, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"✅ Cleanup report saved to: {report_path}")
    return report_path

def main():
    print("🔧 CHAPTER 15 CLEANUP SCRIPT")
    print("=" * 50)
    
    chunks_dir = "data/output/3964f9b1-05b4-4224-b2b5-fccab6ebc8d4/chapter_15_chunks_20250615_223639"
    
    # Step 1: Backup database
    print("\n📦 Step 1: Creating database backup...")
    backup_path = backup_database()
    
    # Step 2: Find regenerated files
    print("\n🔍 Step 2: Scanning for regenerated files...")
    regenerated_files = glob.glob(f'{chunks_dir}/*_REGENERATED.wav')
    chunk_numbers = []
    for file in regenerated_files:
        chunk_num = int(file.split('_chunk_')[1].split('_')[0])
        chunk_numbers.append(chunk_num)
    
    chunk_numbers.sort()
    print(f"Found {len(chunk_numbers)} regenerated files: {chunk_numbers}")
    
    # Step 3: Verify audio files
    print("\n✅ Step 3: Verifying audio files...")
    verified_chunks = verify_audio_files(chunks_dir, chunk_numbers)
    
    if not verified_chunks:
        print("❌ No valid regenerated files found. Exiting.")
        return
    
    # Step 4: Update database
    print("\n💾 Step 4: Updating database...")
    updated_count, total_chunks, completed_chunks = update_database(verified_chunks, chunks_dir)
    
    # Step 5: Rename files
    print("\n📝 Step 5: Renaming regenerated files...")
    renamed_count = rename_regenerated_files(chunks_dir, verified_chunks)
    
    # Step 6: Update database paths
    print("\n🔗 Step 6: Updating database file paths...")
    update_database_paths(chunks_dir, verified_chunks)
    
    # Step 7: Create report
    print("\n📊 Step 7: Creating cleanup report...")
    report_path = create_final_report(backup_path, total_chunks, completed_chunks, updated_count)
    
    # Final summary
    print("\n" + "=" * 50)
    print("🎉 CLEANUP COMPLETED SUCCESSFULLY!")
    print(f"📈 Chapter 15 Status: {completed_chunks}/{total_chunks} chunks ({(completed_chunks/total_chunks)*100:.1f}%)")
    print(f"🔄 Updated {updated_count} chunks from 'failed' to 'completed'")
    print(f"📁 Renamed {renamed_count} audio files")
    print(f"💾 Database backup: {backup_path}")
    print(f"📊 Report: {report_path}")
    
    if completed_chunks == total_chunks:
        print("✅ Chapter 15 is now 100% complete and ready for final audio stitching!")
    else:
        print(f"⚠️  Chapter 15 is {(completed_chunks/total_chunks)*100:.1f}% complete")

if __name__ == "__main__":
    main()