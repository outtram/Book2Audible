"""
Helper methods for the main processor
"""
import time
from typing import List, Dict, Any
from pathlib import Path
from .text_processor import Chapter

class ProcessorHelpers:
    """Helper methods for Book2AudioProcessor"""
    
    @staticmethod
    def generate_summary(input_file: Path, results: List[Dict], 
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
    
    @staticmethod
    def create_manual_chapters(text: str, chapter_breaks: List[str]) -> List[Chapter]:
        """Create chapters based on manual breaks"""
        chapters = []
        current_pos = 0
        
        for i, break_text in enumerate(chapter_breaks):
            chapter_start = text.find(break_text, current_pos)
            if chapter_start == -1:
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
