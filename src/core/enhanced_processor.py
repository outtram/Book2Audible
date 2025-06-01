"""
Enhanced processor with chunk-level management integration
Safely extends the existing processor without breaking current functionality
"""
from pathlib import Path
from typing import List, Dict, Any, Optional
import logging

from .processor import Book2AudioProcessor
from .chunk_manager import ChunkManager
from .text_processor import Chapter

class EnhancedBook2AudioProcessor(Book2AudioProcessor):
    """Enhanced processor with chunk-level management capabilities"""
    
    def __init__(self, log_level: str = "INFO", tts_provider: str = None, enable_chunk_tracking: bool = True):
        super().__init__(log_level, tts_provider)
        
        # Initialize chunk management
        self.enable_chunk_tracking = enable_chunk_tracking
        if enable_chunk_tracking:
            self.chunk_manager = ChunkManager(
                tts_client=self.tts_client,
                audio_processor=self.audio_processor,
                audio_verifier=self.audio_verifier
            )
            self.logger.info("Enhanced processor initialized with chunk tracking")
        else:
            self.chunk_manager = None
            self.logger.info("Enhanced processor initialized without chunk tracking")
    
    def _process_single_chapter(self, chapter: Chapter, output_dir: Path, input_filename: str = None) -> Dict[str, Any]:
        """Enhanced chapter processing with optional chunk tracking"""
        
        # If chunk tracking is disabled, use original method
        if not self.enable_chunk_tracking:
            return super()._process_single_chapter(chapter, output_dir, input_filename)
        
        # Use enhanced processing with chunk tracking
        return self._process_single_chapter_with_tracking(chapter, output_dir, input_filename)
    
    def _process_single_chapter_with_tracking(self, chapter: Chapter, output_dir: Path, input_filename: str = None) -> Dict[str, Any]:
        """Process chapter with full chunk tracking and management"""
        
        # Call the original processing method
        result = super()._process_single_chapter(chapter, output_dir, input_filename)
        
        if result.get('status') != 'success':
            return result
        
        try:
            # Register the chapter in chunk database
            chunks_directory = result.get('chunks_directory', '')
            if chunks_directory:
                chapter_id = self.chunk_manager.register_chapter_processing(
                    input_file=input_filename or "unknown",
                    chapter_number=chapter.number,
                    chapter_title=chapter.title,
                    original_text=chapter.content,
                    chunks_directory=chunks_directory
                )
                
                # Register individual chunks if chunk results exist
                if 'chunk_results' in result:
                    chunk_texts = []
                    for chunk_result in result['chunk_results']:
                        # Extract text from chunk files
                        text_file = chunk_result.get('text_file')
                        if text_file and Path(text_file).exists():
                            with open(text_file, 'r', encoding='utf-8') as f:
                                chunk_texts.append(f.read())
                    
                    if chunk_texts:
                        base_name = Path(input_filename).stem if input_filename else f"Chapter_{chapter.number:02d}"
                        chunks_dir = Path(chunks_directory)
                        
                        chunk_ids = self.chunk_manager.register_chunks(
                            chapter_id=chapter_id,
                            chunks=chunk_texts,
                            base_name=base_name,
                            chunks_dir=chunks_dir
                        )
                        
                        # Update chunk statuses based on results
                        for i, chunk_result in enumerate(result['chunk_results']):
                            if i < len(chunk_ids):
                                chunk_id = chunk_ids[i]
                                verification = chunk_result.get('verification', {})
                                
                                self.chunk_manager.db.update_chunk_status(
                                    chunk_id=chunk_id,
                                    status='completed' if 'error' not in chunk_result else 'failed',
                                    audio_file_path=chunk_result.get('audio_file'),
                                    transcription_file_path=chunk_result.get('transcription_file'),
                                    diff_file_path=chunk_result.get('diff_file'),
                                    verification_score=verification.get('accuracy_score'),
                                    processing_time=chunk_result.get('processing_time'),
                                    error_message=chunk_result.get('error')
                                )
                        
                        # Add chunk management info to result
                        result['chunk_management'] = {
                            'chapter_id': chapter_id,
                            'chunk_ids': chunk_ids,
                            'tracking_enabled': True
                        }
                
                self.logger.info(f"✅ Chapter tracking registered: Chapter ID {chapter_id}")
            
        except Exception as e:
            self.logger.warning(f"⚠️ Chunk tracking failed (processing continued): {e}")
            result['chunk_management'] = {
                'tracking_enabled': False,
                'error': str(e)
            }
        
        return result
    
    def reprocess_chunk_by_id(self, chunk_id: int) -> bool:
        """Reprocess a single chunk by ID"""
        if not self.chunk_manager:
            raise ValueError("Chunk tracking not enabled")
        
        return self.chunk_manager.reprocess_single_chunk(chunk_id)
    
    def reprocess_failed_chunks(self, chapter_id: int) -> Dict[str, Any]:
        """Reprocess all failed chunks in a chapter"""
        if not self.chunk_manager:
            raise ValueError("Chunk tracking not enabled")
        
        return self.chunk_manager.batch_reprocess_failed_chunks(chapter_id)
    
    def get_chapter_chunk_status(self, chapter_id: int) -> Dict[str, Any]:
        """Get detailed chunk status for a chapter"""
        if not self.chunk_manager:
            raise ValueError("Chunk tracking not enabled")
        
        return self.chunk_manager.get_chapter_chunk_status(chapter_id)
    
    def restitch_chapter_audio(self, chapter_id: int, exclude_chunk_ids: List[int] = None) -> str:
        """Restitch chapter audio with optional chunk exclusion"""
        if not self.chunk_manager:
            raise ValueError("Chunk tracking not enabled")
        
        return self.chunk_manager.restitch_chapter_audio(chapter_id, exclude_chunk_ids)
    
    def insert_new_chunk(self, chapter_id: int, position: int, new_text: str, user_title: str = None) -> Optional[int]:
        """Insert a new chunk at specified position"""
        if not self.chunk_manager:
            raise ValueError("Chunk tracking not enabled")
        
        return self.chunk_manager.insert_new_chunk(chapter_id, position, new_text, user_title)
    
    def get_reprocessing_candidates(self, chapter_id: int) -> List[Dict[str, Any]]:
        """Get chunks that might benefit from reprocessing"""
        if not self.chunk_manager:
            raise ValueError("Chunk tracking not enabled")
        
        return self.chunk_manager.get_reprocessing_candidates(chapter_id)