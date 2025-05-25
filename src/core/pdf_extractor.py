#!/usr/bin/env python3
"""
PDF Extractor - Extract chapters from PDF books
Handles chapter detection, text cleaning, and output generation
"""
import re
import fitz  # PyMuPDF
from pathlib import Path
from typing import List, Dict, Tuple, Optional
import logging
from dataclasses import dataclass

@dataclass
class ChapterInfo:
    """Information about an extracted chapter"""
    title: str
    content: str
    start_page: int
    end_page: int
    word_count: int

class PDFExtractor:
    """Extract and clean text from PDF books, separating by chapters"""
    
    # Patterns for detecting chapter breaks
    CHAPTER_PATTERNS = [
        r'^Contents\s*$',
        r'^About the Author\s*$',
        r'^Important Terms of Reference\s*$', 
        r'^Introduction\s*$',
        r'^Chapter \d+\s*$',
        r'^References\s*$'
    ]
    
    # Common header/footer patterns to remove
    HEADER_FOOTER_PATTERNS = [
        r'Using the Brain Science of ADHD as a Guide for Neuro-affirming Practice',
        r'Chapter \d+.*',
        r'^\d+\s*$',  # Page numbers
        r'^\s*\d+\s*$',  # Page numbers with whitespace
        r'^[ivx]+\s*$',  # Roman numerals
        r'^\s*[ivx]+\s*$'  # Roman numerals with whitespace
    ]
    
    def __init__(self, log_level: str = "INFO"):
        """Initialize PDF extractor"""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(getattr(logging, log_level.upper()))
        
    def extract_chapters(self, pdf_path: Path, output_dir: Path) -> Dict[str, any]:
        """
        Extract chapters from PDF and save as separate text files
        
        Args:
            pdf_path: Path to input PDF file
            output_dir: Directory to save extracted chapter files
            
        Returns:
            Dictionary with extraction results and statistics
        """
        self.logger.info(f"Starting PDF extraction: {pdf_path}")
        
        # Create output directory
        chapters_dir = output_dir / "chapters"
        chapters_dir.mkdir(parents=True, exist_ok=True)
        
        # Open PDF
        try:
            doc = fitz.open(pdf_path)
        except Exception as e:
            raise Exception(f"Failed to open PDF: {e}")
        
        # Extract all text with page info
        full_text = self._extract_full_text(doc)
        
        # Detect chapter breaks
        chapters = self._detect_chapters(full_text)
        
        # Clean and save chapters
        saved_chapters = self._save_chapters(chapters, chapters_dir)
        
        # Generate statistics
        stats = self._generate_stats(saved_chapters, doc.page_count)
        
        doc.close()
        
        self.logger.info(f"Extraction complete: {len(saved_chapters)} chapters extracted")
        return stats
    
    def _extract_full_text(self, doc) -> List[Tuple[str, int]]:
        """Extract text from all pages with page numbers"""
        full_text = []
        
        for page_num in range(doc.page_count):
            page = doc[page_num]
            text = page.get_text()
            
            # Split into lines and add page info
            lines = text.split('\n')
            for line in lines:
                if line.strip():  # Skip empty lines
                    full_text.append((line.strip(), page_num + 1))
        
        return full_text
    
    def _detect_chapters(self, full_text: List[Tuple[str, int]]) -> List[ChapterInfo]:
        """Detect chapter boundaries and extract content"""
        chapters = []
        current_chapter = None
        current_content = []
        
        for line, page_num in full_text:
            # Check if this line is a chapter header
            is_chapter_start = self._is_chapter_header(line)
            
            if is_chapter_start:
                # Save previous chapter if exists
                if current_chapter and current_content:
                    content = self._clean_content(current_content)
                    chapters.append(ChapterInfo(
                        title=current_chapter,
                        content=content,
                        start_page=getattr(chapters[-1] if chapters else None, 'end_page', 1),
                        end_page=page_num - 1,
                        word_count=len(content.split())
                    ))
                
                # Start new chapter
                current_chapter = line
                current_content = []
                
            elif current_chapter:
                # Add line to current chapter (if we're in a chapter)
                if not self._is_header_footer(line):
                    current_content.append(line)
        
        # Don't forget the last chapter
        if current_chapter and current_content:
            content = self._clean_content(current_content)
            chapters.append(ChapterInfo(
                title=current_chapter,
                content=content,
                start_page=chapters[-1].end_page + 1 if chapters else 1,
                end_page=999,  # Last page
                word_count=len(content.split())
            ))
        
        return chapters
    
    def _is_chapter_header(self, line: str) -> bool:
        """Check if line matches chapter header patterns"""
        for pattern in self.CHAPTER_PATTERNS:
            if re.match(pattern, line.strip(), re.IGNORECASE):
                return True
        return False
    
    def _is_header_footer(self, line: str) -> bool:
        """Check if line is header/footer that should be removed"""
        for pattern in self.HEADER_FOOTER_PATTERNS:
            if re.match(pattern, line.strip(), re.IGNORECASE):
                return True
        return False
    
    def _clean_content(self, content_lines: List[str]) -> str:
        """Clean and format chapter content"""
        # Filter out headers/footers
        clean_lines = []
        for line in content_lines:
            if not self._is_header_footer(line):
                clean_lines.append(line)
        
        # Join lines and clean up spacing
        content = '\n'.join(clean_lines)
        
        # Remove excessive whitespace
        content = re.sub(r'\n\s*\n\s*\n', '\n\n', content)
        content = re.sub(r'[ \t]+', ' ', content)
        
        return content.strip()
    
    def _save_chapters(self, chapters: List[ChapterInfo], output_dir: Path) -> List[ChapterInfo]:
        """Save chapters as individual text files"""
        saved_chapters = []
        
        for i, chapter in enumerate(chapters):
            # Generate filename
            filename = self._generate_filename(chapter.title, i)
            filepath = output_dir / f"{filename}.txt"
            
            # Skip if content is too short (likely not a real chapter)
            if chapter.word_count < 50:
                self.logger.warning(f"Skipping short chapter: {chapter.title} ({chapter.word_count} words)")
                continue
            
            # Save chapter
            try:
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(chapter.content)
                
                self.logger.info(f"Saved: {filename}.txt ({chapter.word_count} words)")
                saved_chapters.append(chapter)
                
            except Exception as e:
                self.logger.error(f"Failed to save chapter {chapter.title}: {e}")
        
        return saved_chapters
    
    def _generate_filename(self, title: str, index: int) -> str:
        """Generate clean filename from chapter title"""
        # Clean up title for filename
        clean_title = re.sub(r'[^\w\s-]', '', title)
        clean_title = re.sub(r'\s+', '_', clean_title)
        clean_title = clean_title.lower()
        
        # Handle special cases
        if 'contents' in clean_title:
            return 'contents'
        elif 'about_the_author' in clean_title:
            return 'about_the_author'
        elif 'important_terms' in clean_title:
            return 'important_terms'
        elif 'introduction' in clean_title:
            return 'introduction'
        elif 'references' in clean_title:
            return 'references'
        elif 'chapter' in clean_title:
            # Extract chapter number
            match = re.search(r'chapter_(\d+)', clean_title)
            if match:
                return f"chapter_{match.group(1).zfill(2)}"
        
        # Fallback
        return f"section_{str(index + 1).zfill(2)}_{clean_title[:20]}"
    
    def _generate_stats(self, chapters: List[ChapterInfo], total_pages: int) -> Dict[str, any]:
        """Generate extraction statistics"""
        total_words = sum(ch.word_count for ch in chapters)
        
        return {
            'total_chapters': len(chapters),
            'total_words': total_words,
            'total_pages': total_pages,
            'chapters': [
                {
                    'title': ch.title,
                    'filename': self._generate_filename(ch.title, i),
                    'word_count': ch.word_count,
                    'pages': f"{ch.start_page}-{ch.end_page}"
                }
                for i, ch in enumerate(chapters)
            ]
        }


def extract_pdf_chapters(pdf_path: Path, output_dir: Path, log_level: str = "INFO") -> Dict[str, any]:
    """
    Convenience function to extract chapters from PDF
    
    Args:
        pdf_path: Path to input PDF file
        output_dir: Directory to save extracted chapters
        log_level: Logging level
        
    Returns:
        Dictionary with extraction results
    """
    extractor = PDFExtractor(log_level)
    return extractor.extract_chapters(pdf_path, output_dir)
