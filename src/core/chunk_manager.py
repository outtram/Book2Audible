"""
Advanced chunk management for Book2Audible
Enables individual chunk reprocessing, insertion, and selective audio stitching
"""
import time
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import logging
from datetime import datetime

from .chunk_database import ChunkDatabase, ChunkRecord, ChapterRecord, BookProject
from .text_processor import TextProcessor
from .fal_tts_client import FalTTSClient
from .audio_processor import AudioProcessor
from .audio_verifier import AudioVerifier
from .config import config

class ChunkManager:
    """Advanced chunk-level management for cost-effective reprocessing"""
    
    def __init__(self, tts_client=None, audio_processor=None, audio_verifier=None):
        self.logger = logging.getLogger(__name__)
        self.db = ChunkDatabase()
        self.text_processor = TextProcessor()
        self.tts_client = tts_client or FalTTSClient()
        self.audio_processor = audio_processor or AudioProcessor()
        self.audio_verifier = audio_verifier or AudioVerifier()
        
    def register_chapter_processing(self, input_file: str, chapter_number: int, 
                                  chapter_title: str, original_text: str, 
                                  chunks_directory: str) -> int:
        """Register a chapter for chunk-level tracking"""
        
        # Find or create project
        project = self.db.find_project_by_file(input_file)
        if not project:
            project_title = f"Book: {Path(input_file).stem}"
            project_id = self.db.create_project(project_title, input_file)
        else:
            project_id = project.id
            
        # Find or create chapter
        chapter = self.db.find_chapter(project_id, chapter_number)
        if not chapter:
            cleaned_text = self.text_processor.clean_text(original_text)
            chapter_id = self.db.create_chapter(
                project_id=project_id,
                chapter_number=chapter_number,
                title=chapter_title,
                original_text=original_text,
                cleaned_text=cleaned_text,
                chunks_directory=chunks_directory
            )
        else:
            chapter_id = chapter.id
            
        self.logger.info(f"Registered chapter {chapter_id}: {chapter_title}")
        return chapter_id
    
    def register_chunks(self, chapter_id: int, chunks: List[str], 
                       base_name: str, chunks_dir: Path) -> List[int]:
        """Register all chunks for a chapter"""
        chunk_ids = []
        position = 0
        
        for i, chunk_text in enumerate(chunks):
            chunk_number = i + 1
            text_file_path = str(chunks_dir / f"{base_name}_chunk_{chunk_number:03d}.txt")
            
            chunk_id = self.db.create_chunk(
                chapter_id=chapter_id,
                chunk_number=chunk_number,
                position_start=position,
                position_end=position + len(chunk_text),
                original_text=chunk_text,
                cleaned_text=self.text_processor.clean_text(chunk_text),
                text_file_path=text_file_path
            )
            
            chunk_ids.append(chunk_id)
            position += len(chunk_text) + 1  # +1 for space between chunks
            
        self.logger.info(f"Registered {len(chunk_ids)} chunks for chapter {chapter_id}")
        return chunk_ids
    
    def reprocess_single_chunk(self, chunk_id: int) -> bool:
        """Reprocess a single chunk - cost-effective way to fix audio glitches"""
        chunk = self.db.get_chunk(chunk_id)
        if not chunk:
            self.logger.error(f"Chunk {chunk_id} not found")
            return False
            
        chapter = self.db.get_chapter(chunk.chapter_id)
        if not chapter:
            self.logger.error(f"Chapter {chunk.chapter_id} not found")
            return False
            
        self.logger.info(f"Reprocessing chunk {chunk_id}: Chapter {chapter.chapter_number}, Chunk {chunk.chunk_number}")
        
        try:
            # Mark as processing
            self.db.update_chunk_status(chunk_id, 'processing')
            
            start_time = time.time()
            
            # Generate new audio
            chunk_audio = self.tts_client.generate_audio(chunk.cleaned_text)
            
            # Create new file paths with timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            chunks_dir = Path(chapter.chunks_directory)
            base_name = f"chunk_{chunk.chunk_number:03d}"
            
            audio_file_path = chunks_dir / f"{base_name}_REPROCESSED_{timestamp}.wav"
            transcription_file_path = chunks_dir / f"{base_name}_transcription_REPROCESSED_{timestamp}.txt"
            diff_file_path = chunks_dir / f"{base_name}_diff_REPROCESSED_{timestamp}.html"
            
            # Save audio
            self.audio_processor.save_wav_file(chunk_audio, audio_file_path)
            
            # Verify audio
            verification = self.audio_verifier.verify_audio_content(audio_file_path, chunk.cleaned_text)
            
            # Save transcription
            with open(transcription_file_path, 'w', encoding='utf-8') as f:
                f.write(verification.transcribed_text)
            
            # Generate diff
            self._generate_html_diff(chunk.cleaned_text, verification.transcribed_text, 
                                   diff_file_path, f"Chunk {chunk.chunk_number} (Reprocessed)")
            
            processing_time = time.time() - start_time
            
            # Update database
            self.db.update_chunk_status(
                chunk_id=chunk_id,
                status='completed',
                audio_file_path=str(audio_file_path),
                transcription_file_path=str(transcription_file_path),
                diff_file_path=str(diff_file_path),
                verification_score=verification.accuracy_score,
                processing_time=processing_time,
                error_message=None
            )
            
            self.logger.info(f"✅ Successfully reprocessed chunk {chunk_id} (Accuracy: {verification.accuracy_score:.2%})")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Failed to reprocess chunk {chunk_id}: {e}")
            self.db.update_chunk_status(
                chunk_id=chunk_id,
                status='failed',
                error_message=str(e)
            )
            return False
    
    def insert_new_chunk(self, chapter_id: int, position: int, new_text: str, 
                        user_title: str = None) -> Optional[int]:
        """Insert a new chunk at a specific position"""
        chapter = self.db.get_chapter(chapter_id)
        if not chapter:
            self.logger.error(f"Chapter {chapter_id} not found")
            return None
            
        # Clean the new text
        cleaned_text = self.text_processor.clean_text(new_text)
        
        # Insert into database (this shifts existing chunks)
        chunk_id = self.db.insert_chunk_at_position(chapter_id, position, new_text)
        
        # Update the text file path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        chunks_dir = Path(chapter.chunks_directory)
        base_name = f"chunk_{position:03d}"
        
        text_file_path = chunks_dir / f"{base_name}_INSERTED_{timestamp}.txt"
        
        # Save the new text file
        with open(text_file_path, 'w', encoding='utf-8') as f:
            f.write(cleaned_text)
        
        # Update chunk with proper file path  
        with sqlite3.connect(self.db.db_path) as conn:
            conn.execute("""
                UPDATE chunks SET text_file_path = ? WHERE id = ?
            """, (str(text_file_path), chunk_id))
        
        # Log the insertion with user title if provided
        title_info = f" ('{user_title}')" if user_title else ""
        self.logger.info(f"✅ Inserted new chunk {chunk_id} at position {position}{title_info}")
        
        return chunk_id
    
    def get_chapter_chunk_status(self, chapter_id: int) -> Dict[str, Any]:
        """Get detailed status of all chunks in a chapter"""
        chunks = self.db.get_chunks_by_chapter(chapter_id)
        chapter = self.db.get_chapter(chapter_id)
        
        if not chapter:
            return {}
        
        chunk_status = []
        for chunk in chunks:
            status_info = {
                'chunk_id': chunk.id,
                'chunk_number': chunk.chunk_number,
                'status': chunk.status,
                'verification_score': chunk.verification_score,
                'processing_time': chunk.processing_time,
                'error_message': chunk.error_message,
                'has_audio': bool(chunk.audio_file_path and Path(chunk.audio_file_path).exists()),
                'text_length': len(chunk.original_text),
                'word_count': len(chunk.original_text.split()),
                'needs_attention': chunk.status in ['failed', 'needs_reprocess'] or 
                                 (chunk.verification_score and chunk.verification_score < 0.85)
            }
            chunk_status.append(status_info)
        
        summary = self.db.get_chapter_summary(chapter_id)
        
        return {
            'chapter_id': chapter_id,
            'chapter_number': chapter.chapter_number,
            'chapter_title': chapter.title,
            'chunks_directory': chapter.chunks_directory,
            'summary': summary,
            'chunks': chunk_status
        }
    
    def restitch_chapter_audio(self, chapter_id: int, exclude_chunk_ids: List[int] = None) -> str:
        """Restitch chapter audio, optionally excluding problematic chunks"""
        chapter = self.db.get_chapter(chapter_id)
        chunks = self.db.get_chunks_by_chapter(chapter_id)
        
        if not chapter or not chunks:
            raise ValueError(f"Chapter {chapter_id} or chunks not found")
        
        exclude_chunk_ids = exclude_chunk_ids or []
        
        # Collect audio data from completed chunks
        audio_chunks = []
        included_chunks = []
        
        for chunk in chunks:
            if chunk.id in exclude_chunk_ids:
                self.logger.info(f"⏭️ Excluding chunk {chunk.chunk_number} from stitching")
                continue
                
            if chunk.status != 'completed' or not chunk.audio_file_path:
                self.logger.warning(f"⚠️ Chunk {chunk.chunk_number} not ready - skipping")
                continue
                
            audio_path = Path(chunk.audio_file_path)
            if not audio_path.exists():
                self.logger.warning(f"⚠️ Audio file missing for chunk {chunk.chunk_number}: {audio_path}")
                continue
            
            # Load audio data
            with open(audio_path, 'rb') as f:
                audio_data = f.read()
                audio_chunks.append(audio_data)
                included_chunks.append(chunk.chunk_number)
        
        if not audio_chunks:
            raise ValueError("No valid audio chunks found for stitching")
        
        self.logger.info(f"Stitching {len(audio_chunks)} chunks: {included_chunks}")
        
        # Stitch audio
        if len(audio_chunks) == 1:
            final_audio = audio_chunks[0]
        else:
            final_audio = self.audio_processor.stitch_audio_chunks(audio_chunks)
        
        # Save new stitched file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        chunks_dir = Path(chapter.chunks_directory)
        output_filename = f"Chapter_{chapter.chapter_number:02d}_RESTITCHED_{timestamp}.wav"
        output_path = chunks_dir / output_filename
        
        self.audio_processor.save_wav_file(final_audio, output_path)
        
        # Register the new stitched audio version in the database
        chunk_ids = [chunk.id for chunk in chunks if chunk.id not in exclude_chunk_ids]
        processing_log = f"Restitched from {len(included_chunks)} chunks. Excluded: {len(exclude_chunk_ids)} chunks."
        
        version_id = self.db.create_chapter_audio_version(
            chapter_id=chapter_id,
            audio_file_path=str(output_path),
            stitched_from_chunks=chunk_ids,
            excluded_chunks=exclude_chunk_ids,
            processing_log=processing_log
        )
        
        self.logger.info(f"✅ Restitched chapter audio: {output_path}")
        self.logger.info(f"📊 Included chunks: {included_chunks}")
        self.logger.info(f"🗄️ Registered as database version {version_id}")
        if exclude_chunk_ids:
            excluded_numbers = [self.db.get_chunk(cid).chunk_number for cid in exclude_chunk_ids if self.db.get_chunk(cid)]
            self.logger.info(f"🚫 Excluded chunks: {excluded_numbers}")
        
        return str(output_path)
    
    def batch_reprocess_failed_chunks(self, chapter_id: int) -> Dict[str, Any]:
        """Reprocess all failed or low-quality chunks in a chapter"""
        chunks = self.db.get_chunks_needing_reprocessing(chapter_id)
        
        # Also include low-quality chunks
        all_chunks = self.db.get_chunks_by_chapter(chapter_id)
        for chunk in all_chunks:
            if (chunk.verification_score and chunk.verification_score < 0.85 and 
                chunk.status == 'completed' and chunk not in chunks):
                chunks.append(chunk)
        
        if not chunks:
            self.logger.info(f"No chunks need reprocessing in chapter {chapter_id}")
            return {'reprocessed': 0, 'failed': 0, 'chunks': []}
        
        results = {'reprocessed': 0, 'failed': 0, 'chunks': []}
        
        for chunk in chunks:
            self.logger.info(f"Reprocessing chunk {chunk.chunk_number}...")
            
            # Add delay between chunks
            chunk_delay = config.tts_settings.get("chunk_delay", 2)
            if results['reprocessed'] > 0:
                time.sleep(chunk_delay)
            
            success = self.reprocess_single_chunk(chunk.id)
            
            if success:
                results['reprocessed'] += 1
            else:
                results['failed'] += 1
            
            results['chunks'].append({
                'chunk_id': chunk.id,
                'chunk_number': chunk.chunk_number,
                'success': success
            })
        
        self.logger.info(f"Batch reprocessing complete: {results['reprocessed']} success, {results['failed']} failed")
        return results
    
    def _generate_html_diff(self, original_text: str, transcribed_text: str, 
                           diff_file: Path, chunk_title: str):
        """Generate HTML diff file for chunk comparison"""
        import difflib
        
        original_words = original_text.split()
        transcribed_words = transcribed_text.split()
        
        differ = difflib.HtmlDiff(tabsize=2)
        diff_html = differ.make_file(
            original_words,
            transcribed_words,
            fromdesc=f"Original Text ({chunk_title})",
            todesc=f"Transcribed Audio ({chunk_title})",
            context=True,
            numlines=3
        )
        
        # Add custom CSS
        custom_css = """
        <style>
        body { font-family: Arial, sans-serif; margin: 20px; }
        .diff_header { background-color: #f0f0f0; padding: 10px; border-radius: 5px; margin-bottom: 10px; }
        table.diff { border-collapse: collapse; width: 100%; }
        .diff_add { background-color: #aaffaa; }
        .diff_chg { background-color: #ffff77; }
        .diff_sub { background-color: #ffaaaa; }
        .summary { background-color: #e8f4fd; padding: 15px; border-radius: 5px; margin: 10px 0; }
        </style>
        """
        
        # Calculate accuracy
        comparison = self.audio_verifier._compare_texts(original_text, transcribed_text)
        
        summary_html = f"""
        <div class="summary">
            <h3>Verification Summary - {chunk_title}</h3>
            <p><strong>Accuracy Score:</strong> {comparison.accuracy_score:.2%}</p>
            <p><strong>Status:</strong> {'✅ PASSED' if comparison.accuracy_score >= 0.85 else '❌ FAILED'}</p>
        </div>
        """
        
        diff_html = diff_html.replace('<head>', f'<head>{custom_css}')
        diff_html = diff_html.replace('<body>', f'<body>{summary_html}')
        
        with open(diff_file, 'w', encoding='utf-8') as f:
            f.write(diff_html)
    
    def mark_chunk_for_reprocessing(self, chunk_id: int, reason: str = "User requested"):
        """Mark a specific chunk for reprocessing"""
        self.db.mark_chunk_for_reprocessing(chunk_id, reason)
        chunk = self.db.get_chunk(chunk_id)
        if chunk:
            self.logger.info(f"Marked chunk {chunk.chunk_number} for reprocessing: {reason}")
    
    def get_reprocessing_candidates(self, chapter_id: int) -> List[Dict[str, Any]]:
        """Get chunks that might benefit from reprocessing"""
        chunks = self.db.get_chunks_by_chapter(chapter_id)
        candidates = []
        
        for chunk in chunks:
            needs_reprocess = False
            reason = []
            
            if chunk.status == 'failed':
                needs_reprocess = True
                reason.append("Failed processing")
            elif chunk.status == 'needs_reprocess':
                needs_reprocess = True
                reason.append("Marked for reprocessing")
            elif chunk.verification_score and chunk.verification_score < 0.85:
                needs_reprocess = True
                reason.append(f"Low accuracy ({chunk.verification_score:.1%})")
            elif not chunk.audio_file_path or not Path(chunk.audio_file_path).exists():
                needs_reprocess = True
                reason.append("Missing audio file")
            
            if needs_reprocess:
                candidates.append({
                    'chunk_id': chunk.id,
                    'chunk_number': chunk.chunk_number,
                    'status': chunk.status,
                    'verification_score': chunk.verification_score,
                    'reasons': reason,
                    'text_preview': chunk.original_text[:100] + "..." if len(chunk.original_text) > 100 else chunk.original_text
                })
        
        return candidates