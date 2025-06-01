#!/usr/bin/env python3
"""
CLI tool for chunk-level operations in Book2Audible
Enables cost-effective reprocessing of individual chunks
"""
import argparse
import sys
from pathlib import Path
from typing import List

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from src.core.chunk_manager import ChunkManager
from src.core.chunk_database import ChunkDatabase
from src.utils.logger import setup_logger

def main():
    parser = argparse.ArgumentParser(description="Book2Audible Chunk Management CLI")
    subparsers = parser.add_subparsers(dest='command', help='Available commands')
    
    # List chapters command
    list_parser = subparsers.add_parser('list-chapters', help='List all chapters')
    list_parser.add_argument('--project-id', type=int, help='Filter by project ID')
    
    # Chapter status command
    status_parser = subparsers.add_parser('chapter-status', help='Get chapter chunk status')
    status_parser.add_argument('chapter_id', type=int, help='Chapter ID')
    
    # Reprocess chunk command
    reprocess_parser = subparsers.add_parser('reprocess-chunk', help='Reprocess a single chunk')
    reprocess_parser.add_argument('chunk_id', type=int, help='Chunk ID to reprocess')
    
    # Reprocess failed command
    failed_parser = subparsers.add_parser('reprocess-failed', help='Reprocess all failed chunks')
    failed_parser.add_argument('chapter_id', type=int, help='Chapter ID')
    
    # Insert chunk command
    insert_parser = subparsers.add_parser('insert-chunk', help='Insert new chunk at position')
    insert_parser.add_argument('chapter_id', type=int, help='Chapter ID')
    insert_parser.add_argument('position', type=int, help='Position to insert at (1-based)')
    insert_parser.add_argument('text', help='Text content for new chunk')
    insert_parser.add_argument('--title', help='Optional title for the chunk')
    
    # Restitch command
    restitch_parser = subparsers.add_parser('restitch', help='Restitch chapter audio')
    restitch_parser.add_argument('chapter_id', type=int, help='Chapter ID')
    restitch_parser.add_argument('--exclude', type=int, nargs='*', help='Chunk IDs to exclude')
    
    # Mark for reprocessing command
    mark_parser = subparsers.add_parser('mark-reprocess', help='Mark chunk for reprocessing')
    mark_parser.add_argument('chunk_id', type=int, help='Chunk ID')
    mark_parser.add_argument('--reason', default='User requested', help='Reason for reprocessing')
    
    # Show candidates command
    candidates_parser = subparsers.add_parser('show-candidates', help='Show reprocessing candidates')
    candidates_parser.add_argument('chapter_id', type=int, help='Chapter ID')
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # Setup logging
    logger = setup_logger("ChunkCLI", Path("data/logs/chunk_cli.log"), "INFO")
    
    # Initialize managers
    db = ChunkDatabase()
    chunk_manager = ChunkManager()
    
    try:
        if args.command == 'list-chapters':
            list_chapters(db, args.project_id)
            
        elif args.command == 'chapter-status':
            show_chapter_status(chunk_manager, args.chapter_id)
            
        elif args.command == 'reprocess-chunk':
            reprocess_single_chunk(chunk_manager, args.chunk_id)
            
        elif args.command == 'reprocess-failed':
            reprocess_failed_chunks(chunk_manager, args.chapter_id)
            
        elif args.command == 'insert-chunk':
            insert_new_chunk(chunk_manager, args.chapter_id, args.position, args.text, args.title)
            
        elif args.command == 'restitch':
            restitch_audio(chunk_manager, args.chapter_id, args.exclude)
            
        elif args.command == 'mark-reprocess':
            mark_for_reprocessing(chunk_manager, args.chunk_id, args.reason)
            
        elif args.command == 'show-candidates':
            show_reprocessing_candidates(chunk_manager, args.chapter_id)
            
    except Exception as e:
        logger.error(f"Command failed: {e}")
        print(f"❌ Error: {e}")
        sys.exit(1)

def list_chapters(db: ChunkDatabase, project_id: int = None):
    """List all chapters with basic info"""
    import sqlite3
    with sqlite3.connect(db.db_path) as conn:
        if project_id:
            cursor = conn.execute("""
                SELECT c.id, c.chapter_number, c.title, c.status, c.chunks_directory,
                       p.title as project_title
                FROM chapters c
                JOIN projects p ON c.project_id = p.id
                WHERE c.project_id = ?
                ORDER BY c.chapter_number
            """, (project_id,))
        else:
            cursor = conn.execute("""
                SELECT c.id, c.chapter_number, c.title, c.status, c.chunks_directory,
                       p.title as project_title
                FROM chapters c
                JOIN projects p ON c.project_id = p.id
                ORDER BY p.id, c.chapter_number
            """)
        
        chapters = cursor.fetchall()
    
    if not chapters:
        print("No chapters found.")
        return
    
    print(f"\n📚 Found {len(chapters)} chapters:")
    print("-" * 80)
    
    current_project = None
    for chapter in chapters:
        chapter_id, chapter_num, title, status, chunks_dir, project_title = chapter
        
        if project_title != current_project:
            print(f"\n📖 Project: {project_title}")
            current_project = project_title
        
        status_emoji = {
            'pending': '⏳',
            'processing': '🔄', 
            'completed': '✅',
            'failed': '❌'
        }.get(status, '❓')
        
        print(f"  {status_emoji} Chapter {chapter_num:2d} (ID: {chapter_id:3d}): {title}")
        print(f"     📁 {chunks_dir}")

def show_chapter_status(chunk_manager: ChunkManager, chapter_id: int):
    """Show detailed status of chapter chunks"""
    status = chunk_manager.get_chapter_chunk_status(chapter_id)
    
    if not status:
        print(f"❌ Chapter {chapter_id} not found")
        return
    
    print(f"\n📊 Chapter {status['chapter_number']}: {status['chapter_title']}")
    print(f"📁 Directory: {status['chunks_directory']}")
    print("-" * 60)
    
    summary = status['summary']
    print(f"📈 Summary:")
    print(f"  Total chunks: {summary['total_chunks']}")
    print(f"  Completed: {summary['completed_chunks']}")
    print(f"  Failed: {summary['failed_chunks']}")
    print(f"  Need reprocessing: {summary['reprocess_chunks']}")
    
    if summary['avg_verification_score']:
        print(f"  Avg accuracy: {summary['avg_verification_score']:.1%}")
    
    print(f"\n🔍 Chunk Details:")
    
    for chunk in status['chunks']:
        status_emoji = {
            'pending': '⏳',
            'processing': '🔄',
            'completed': '✅',
            'failed': '❌',
            'needs_reprocess': '🔄'
        }.get(chunk['status'], '❓')
        
        attention = "⚠️ " if chunk['needs_attention'] else ""
        audio_status = "🎵" if chunk['has_audio'] else "🚫"
        
        accuracy = ""
        if chunk['verification_score']:
            accuracy = f" ({chunk['verification_score']:.1%})"
        
        print(f"  {attention}{status_emoji} Chunk {chunk['chunk_number']:3d} (ID: {chunk['chunk_id']:3d}): "
              f"{chunk['word_count']:3d} words {audio_status}{accuracy}")
        
        if chunk['error_message']:
            print(f"      ❌ Error: {chunk['error_message'][:50]}...")

def reprocess_single_chunk(chunk_manager: ChunkManager, chunk_id: int):
    """Reprocess a single chunk"""
    print(f"🔄 Reprocessing chunk {chunk_id}...")
    
    success = chunk_manager.reprocess_single_chunk(chunk_id)
    
    if success:
        print(f"✅ Successfully reprocessed chunk {chunk_id}")
    else:
        print(f"❌ Failed to reprocess chunk {chunk_id}")

def reprocess_failed_chunks(chunk_manager: ChunkManager, chapter_id: int):
    """Reprocess all failed chunks in a chapter"""
    print(f"🔄 Reprocessing failed chunks in chapter {chapter_id}...")
    
    results = chunk_manager.batch_reprocess_failed_chunks(chapter_id)
    
    print(f"\n📊 Batch reprocessing results:")
    print(f"  ✅ Successfully reprocessed: {results['reprocessed']}")
    print(f"  ❌ Failed to reprocess: {results['failed']}")
    
    if results['chunks']:
        print(f"\n🔍 Details:")
        for chunk_result in results['chunks']:
            status = "✅" if chunk_result['success'] else "❌"
            print(f"  {status} Chunk {chunk_result['chunk_number']} (ID: {chunk_result['chunk_id']})")

def insert_new_chunk(chunk_manager: ChunkManager, chapter_id: int, position: int, text: str, title: str = None):
    """Insert a new chunk at specified position"""
    print(f"➕ Inserting new chunk at position {position} in chapter {chapter_id}...")
    
    if title:
        print(f"📝 Title: {title}")
    
    print(f"📄 Text: {text[:100]}{'...' if len(text) > 100 else ''}")
    
    chunk_id = chunk_manager.insert_new_chunk(chapter_id, position, text, title)
    
    if chunk_id:
        print(f"✅ Successfully inserted chunk {chunk_id} at position {position}")
        print(f"💡 Remember to process this chunk with: python chunk_cli.py reprocess-chunk {chunk_id}")
    else:
        print(f"❌ Failed to insert chunk")

def restitch_audio(chunk_manager: ChunkManager, chapter_id: int, exclude_chunk_ids: List[int] = None):
    """Restitch chapter audio"""
    exclude_chunk_ids = exclude_chunk_ids or []
    
    print(f"🎵 Restitching audio for chapter {chapter_id}...")
    if exclude_chunk_ids:
        print(f"🚫 Excluding chunks: {exclude_chunk_ids}")
    
    try:
        output_path = chunk_manager.restitch_chapter_audio(chapter_id, exclude_chunk_ids)
        print(f"✅ Successfully restitched audio: {output_path}")
    except Exception as e:
        print(f"❌ Failed to restitch audio: {e}")

def mark_for_reprocessing(chunk_manager: ChunkManager, chunk_id: int, reason: str):
    """Mark chunk for reprocessing"""
    print(f"🏷️ Marking chunk {chunk_id} for reprocessing...")
    print(f"📝 Reason: {reason}")
    
    chunk_manager.mark_chunk_for_reprocessing(chunk_id, reason)
    print(f"✅ Chunk {chunk_id} marked for reprocessing")

def show_reprocessing_candidates(chunk_manager: ChunkManager, chapter_id: int):
    """Show chunks that might benefit from reprocessing"""
    candidates = chunk_manager.get_reprocessing_candidates(chapter_id)
    
    if not candidates:
        print(f"✅ No chunks need reprocessing in chapter {chapter_id}")
        return
    
    print(f"\n⚠️ Found {len(candidates)} chunks that might need reprocessing:")
    print("-" * 60)
    
    for candidate in candidates:
        reasons_str = ", ".join(candidate['reasons'])
        print(f"🔍 Chunk {candidate['chunk_number']} (ID: {candidate['chunk_id']})")
        print(f"   Status: {candidate['status']}")
        print(f"   Reasons: {reasons_str}")
        
        if candidate['verification_score']:
            print(f"   Accuracy: {candidate['verification_score']:.1%}")
        
        print(f"   Text: {candidate['text_preview']}")
        print()
    
    print(f"💡 To reprocess all candidates: python chunk_cli.py reprocess-failed {chapter_id}")

if __name__ == "__main__":
    main()