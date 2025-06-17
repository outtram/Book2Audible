#!/usr/bin/env python3
"""
Create Final Stitched Audio for Chapter 15
Combines all 101 audio chunks into a single chapter audio file
"""

import os
import sqlite3
from pydub import AudioSegment
from datetime import datetime
import json

def get_chapter_chunks():
    """Get all completed chunks for chapter 15 in order"""
    conn = sqlite3.connect('data/chunk_database.db')
    cursor = conn.cursor()
    
    cursor.execute("""
        SELECT chunk_number, audio_file_path 
        FROM chunks 
        WHERE chapter_id = 7 AND status = 'completed' 
        ORDER BY chunk_number
    """)
    
    chunks = cursor.fetchall()
    conn.close()
    
    return chunks

def stitch_audio_chunks(chunks, output_path):
    """Stitch all audio chunks together"""
    print(f"🎵 Stitching {len(chunks)} audio chunks...")
    
    # Start with empty audio
    final_audio = AudioSegment.empty()
    
    for i, (chunk_num, audio_path) in enumerate(chunks):
        if not os.path.exists(audio_path):
            print(f"⚠️  Warning: Missing audio file for chunk {chunk_num}: {audio_path}")
            continue
        
        try:
            # Load audio chunk
            chunk_audio = AudioSegment.from_wav(audio_path)
            
            # Add to final audio
            final_audio += chunk_audio
            
            # Progress indicator
            if (i + 1) % 10 == 0:
                print(f"  ✅ Processed {i + 1}/{len(chunks)} chunks")
                
        except Exception as e:
            print(f"❌ Error processing chunk {chunk_num}: {e}")
            continue
    
    # Export final audio
    print(f"💾 Exporting final audio to: {output_path}")
    final_audio.export(output_path, format="wav")
    
    # Get audio info
    duration_seconds = len(final_audio) / 1000
    duration_minutes = duration_seconds / 60
    file_size_mb = os.path.getsize(output_path) / (1024 * 1024)
    
    print(f"✅ Final audio created successfully!")
    print(f"  📏 Duration: {duration_minutes:.1f} minutes ({duration_seconds:.1f} seconds)")
    print(f"  📦 File size: {file_size_mb:.1f} MB")
    
    return {
        "duration_seconds": duration_seconds,
        "duration_minutes": duration_minutes,
        "file_size_mb": file_size_mb,
        "chunks_processed": len(chunks)
    }

def create_metadata_file(output_path, audio_info):
    """Create metadata file for the final audio"""
    metadata = {
        "chapter_number": 15,
        "title": "A Pathway Towards Wholeness",
        "audio_file": output_path,
        "created_at": datetime.now().isoformat(),
        "total_chunks": audio_info["chunks_processed"],
        "duration_seconds": audio_info["duration_seconds"],
        "duration_minutes": audio_info["duration_minutes"],
        "file_size_mb": audio_info["file_size_mb"],
        "format": "WAV",
        "sample_rate": "22050 Hz",
        "channels": "Mono",
        "source": "FAL TTS + Regenerated chunks after credit exhaustion"
    }
    
    metadata_path = output_path.replace('.wav', '_metadata.json')
    with open(metadata_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"📋 Metadata saved to: {metadata_path}")
    return metadata_path

def main():
    print("🎵 CHAPTER 15 FINAL AUDIO CREATION")
    print("=" * 50)
    
    # Get chunks from database
    print("\n📊 Step 1: Getting chunk information from database...")
    chunks = get_chapter_chunks()
    
    if not chunks:
        print("❌ No completed chunks found for chapter 15")
        return
    
    print(f"✅ Found {len(chunks)} completed chunks")
    
    # Verify all audio files exist
    print("\n🔍 Step 2: Verifying audio files...")
    missing_files = []
    for chunk_num, audio_path in chunks:
        if not os.path.exists(audio_path):
            missing_files.append((chunk_num, audio_path))
    
    if missing_files:
        print(f"⚠️  Warning: {len(missing_files)} audio files are missing:")
        for chunk_num, path in missing_files[:5]:  # Show first 5
            print(f"    Chunk {chunk_num}: {path}")
        if len(missing_files) > 5:
            print(f"    ... and {len(missing_files) - 5} more")
    else:
        print("✅ All audio files verified")
    
    # Create output directory
    output_dir = "data/output/final_chapters"
    os.makedirs(output_dir, exist_ok=True)
    
    # Define output path
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = f"{output_dir}/chapter_15_complete_{timestamp}.wav"
    
    # Stitch audio
    print(f"\n🎵 Step 3: Stitching audio chunks...")
    try:
        audio_info = stitch_audio_chunks(chunks, output_path)
        
        # Create metadata
        print(f"\n📋 Step 4: Creating metadata...")
        metadata_path = create_metadata_file(output_path, audio_info)
        
        # Final summary
        print("\n" + "=" * 50)
        print("🎉 CHAPTER 15 FINAL AUDIO COMPLETED!")
        print(f"🎵 Audio file: {output_path}")
        print(f"📋 Metadata: {metadata_path}")
        print(f"📏 Duration: {audio_info['duration_minutes']:.1f} minutes")
        print(f"📦 Size: {audio_info['file_size_mb']:.1f} MB")
        print(f"🔢 Chunks: {audio_info['chunks_processed']}")
        
    except Exception as e:
        print(f"❌ Error creating final audio: {e}")
        return

if __name__ == "__main__":
    main()