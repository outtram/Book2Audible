"""
Main processing engine for Book2Audible
"""
import json
import time
from pathlib import Path
from typing import List, Dict, Any
import logging
from tqdm import tqdm

from .config import config
from .text_processor import TextProcessor, Chapter
from .tts_client import BaseTenTTSClient
from .audio_processor import AudioProcessor
from .helpers import ProcessorHelpers
from ..utils.file_handler import FileHandler
from ..utils.logger import setup_logger

class Book2AudioProcessor:
    """Main processor orchestrating the text-to-audio conversion"""
    
    def __init__(self, log_level: str = "INFO"):
        # Setup logging
        self.logger = setup_logger("Book2Audio", config.log_file, log_level)
        
        # Initialize components
        self.text_processor = TextProcessor()
        self.tts_client = BaseTenTTSClient()
        self.audio_processor = AudioProcessor()
        self.file_handler = FileHandler()
        
        self.logger.info("Book2Audio processor initialized")
    
    def process_book(self, input_file: Path, output_dir: Path = None, 
                     manual_chapters: List[str] = None) -> Dict[str, Any]:
        """Process entire book from text file to audio chapters"""
        
        output_dir = output_dir or config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Starting book processing: {input_file}")
        self.logger.info(f"Output directory: {output_dir}")
        
        try:
            # Step 1: Read input file
            self.logger.info("Reading input file...")
            text_content = self.file_handler.read_file(input_file)
            self.logger.info(f"File read successfully: {len(text_content)} characters")
            
            # Step 2: Detect chapters
            self.logger.info("Detecting chapters...")
            if manual_chapters:
                chapters = self._create_manual_chapters(text_content, manual_chapters)
            else:
                chapters = self.text_processor.detect_chapters(text_content)
            
            self.logger.info(f"Found {len(chapters)} chapters")
            
            # Step 3: Process each chapter
            processing_results = []
            chapter_files = []
            
            for chapter in tqdm(chapters, desc="Processing chapters"):
                self.logger.info(f"Processing Chapter {chapter.number}: {chapter.title}")
                
                try:
                    result = self._process_single_chapter(chapter, output_dir)
                    processing_results.append(result)
                    chapter_files.append(result['audio_file'])
                    
                except Exception as e:
                    self.logger.error(f"Failed to process chapter {chapter.number}: {e}")
                    processing_results.append({
                        'chapter': chapter.number,
                        'status': 'failed',
                        'error': str(e)
                    })
        
            # Generate summary and save log
            summary = self._generate_summary(input_file, processing_results, chapter_files)
            log_file = output_dir / f"{input_file.stem}_processing_log.json"
            with open(log_file, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            
            self.logger.info("Book processing completed!")
            return summary
            
        except Exception as e:
            self.logger.error(f"Book processing failed: {e}")
            raise
    
    def process_book(self, input_file: Path, output_dir: Path = None, 
                     manual_chapters: List[str] = None) -> Dict[str, Any]:
        """Process entire book from text file to audio chapters"""
        
        output_dir = output_dir or config.output_dir
        output_dir.mkdir(parents=True, exist_ok=True)
        
        self.logger.info(f"Starting book processing: {input_file}")
        
        try:
            # Read and process text
            text_content = self.file_handler.read_file(input_file)
            self.logger.info(f"File read: {len(text_content)} characters")
            
            if manual_chapters:
                chapters = ProcessorHelpers.create_manual_chapters(text_content, manual_chapters)
            else:
                chapters = self.text_processor.detect_chapters(text_content)
            
            self.logger.info(f"Found {len(chapters)} chapters")
            
            # Process chapters
            processing_results = []
            chapter_files = []
            
            for chapter in tqdm(chapters, desc="Processing chapters"):
                try:
                    result = self._process_single_chapter(chapter, output_dir)
                    processing_results.append(result)
                    chapter_files.append(result['audio_file'])
                except Exception as e:
                    self.logger.error(f"Chapter {chapter.number} failed: {e}")
                    processing_results.append({
                        'chapter': chapter.number, 'status': 'failed', 'error': str(e)
                    })
            
            # Generate summary
            summary = ProcessorHelpers.generate_summary(input_file, processing_results, chapter_files)
            log_file = output_dir / f"{input_file.stem}_log.json"
            with open(log_file, 'w') as f:
                json.dump(summary, f, indent=2, default=str)
            
            self.logger.info("Processing completed!")
            return summary
            
        except Exception as e:
            self.logger.error(f"Processing failed: {e}")
            raise

    def _process_single_chapter(self, chapter: Chapter, output_dir: Path) -> Dict[str, Any]:
        """Process a single chapter to audio"""
        chapter_start_time = time.time()
        
        # Clean text
        cleaned_text = self.text_processor.clean_text(chapter.content)
        
        # Split into chunks if needed
        chunks = self.text_processor.chunk_long_text(cleaned_text, config.chunk_size)
        self.logger.info(f"Chapter {chapter.number} split into {len(chunks)} chunks")
        
        # Generate audio for each chunk
        audio_chunks = self.tts_client.batch_generate(chunks)
        
        # Stitch audio chunks together
        if len(audio_chunks) > 1:
            final_audio = self.audio_processor.stitch_audio_chunks(audio_chunks)
        else:
            final_audio = audio_chunks[0]
        
        # Save audio file
        filename = f"Chapter_{chapter.number:02d}.wav"
        if chapter.title:
            safe_title = "".join(c for c in chapter.title if c.isalnum() or c in (' ', '-', '_')).strip()
            filename = f"Chapter_{chapter.number:02d}_{safe_title}.wav"
        
        output_path = output_dir / filename
        self.audio_processor.save_wav_file(final_audio, output_path)
        
        # Validate audio quality
        quality_info = self.audio_processor.validate_audio_quality(output_path)
        
        processing_time = time.time() - chapter_start_time
        
        return {
            'chapter': chapter.number,
            'title': chapter.title,
            'word_count': chapter.word_count,
            'chunk_count': len(chunks),
            'audio_file': str(output_path),
            'processing_time': processing_time,
            'quality_check': quality_info,
            'status': 'success'
        }

    def _generate_summary(self, input_file: Path, results: List[Dict], 
                         chapter_files: List[str]) -> Dict[str, Any]:
        """Generate processing summary report"""
        successful_chapters = [r for r in results if r.get('status') == 'success']
        failed_chapters = [r for r in results if r.get('status') == 'failed']
        
        total_words = sum(r.get('word_count', 0) for r in successful_chapters)
        total_time = sum(r.get('processing_time', 0) for r in successful_chapters)
        
        return {
            'input_file': str(input_file),
            'processing_date': time.strftime('%Y-%m-%d %H:%M:%S'),
            'total_chapters': len(results),
            'successful_chapters': len(successful_chapters),
            'failed_chapters': len(failed_chapters),
            'total_words_processed': total_words,
            'total_processing_time': total_time,
            'average_time_per_chapter': total_time / len(successful_chapters) if successful_chapters else 0,
            'output_files': chapter_files,
            'chapter_details': results
        }
    
    def _create_manual_chapters(self, text: str, chapter_breaks: List[str]) -> List[Chapter]:
        """Create chapters based on manual breaks"""
        chapters = []
        current_pos = 0
        
        for i, break_text in enumerate(chapter_breaks):
            chapter_start = text.find(break_text, current_pos)
            if chapter_start == -1:
                self.logger.warning(f"Chapter break not found: {break_text}")
                continue
            
            # Get previous chapter content
            if i > 0:
                prev_chapter = chapters[-1]
                prev_chapter.content = text[prev_chapter.start_position:chapter_start].strip()
                prev_chapter.end_position = chapter_start
                prev_chapter.word_count = len(prev_chapter.content.split())
            
            # Create new chapter
            chapter = Chapter(
                number=i + 1,
                title=break_text.strip(),
                content="",
                start_position=chapter_start,
                end_position=0,
                word_count=0
            )
            chapters.append(chapter)
            current_pos = chapter_start
        
        # Handle last chapter
        if chapters:
            last_chapter = chapters[-1]
            last_chapter.content = text[last_chapter.start_position:].strip()
            last_chapter.end_position = len(text)
            last_chapter.word_count = len(last_chapter.content.split())
        
        return chapters
