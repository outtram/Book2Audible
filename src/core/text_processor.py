"""
Text processing for Book2Audible - Chapter detection and text cleaning
"""
import re
import nltk
from typing import List, Tuple, Dict, Optional, Union
from dataclasses import dataclass
from pathlib import Path

# Download required NLTK data
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')

@dataclass
class Chapter:
    """Represents a book chapter"""
    number: int
    title: str
    content: str
    start_position: int
    end_position: int
    word_count: int

class TextProcessor:
    """Handles text processing, chapter detection, and cleaning"""
    
    def __init__(self):
        self.chapter_patterns = [
            r'^Chapter\s+(\d+)[\.\:\-\s]*(.*)$',
            r'^CHAPTER\s+(\d+)[\.\:\-\s]*(.*)$',
            r'^Ch\.\s*(\d+)[\.\:\-\s]*(.*)$',
            r'^(\d+)[\.\:\-\s]+(.*)$',
            r'^Part\s+(\d+)[\.\:\-\s]*(.*)$',
            r'^PART\s+(\d+)[\.\:\-\s]*(.*)$',
        ]
        
        # Australian English specific terms to preserve
        self.au_spellings = {
            'color': 'colour', 'favor': 'favour', 'honor': 'honour',
            'labor': 'labour', 'organize': 'organise', 'recognize': 'recognise',
            'realize': 'realise', 'analyze': 'analyse', 'center': 'centre',
            'theater': 'theatre',
        }
    
    def detect_chapters(self, text: str) -> List[Chapter]:
        """Detect chapters in the text"""
        chapters = []
        lines = text.split('\n')
        current_chapter = None
        current_content = []
        
        for i, line in enumerate(lines):
            line = line.strip()
            
            # Check if line matches chapter pattern
            chapter_match = self._is_chapter_heading(line)
            
            if chapter_match:
                # Save previous chapter if exists
                if current_chapter:
                    chapter_content = '\n'.join(current_content).strip()
                    current_chapter.content = chapter_content
                    current_chapter.end_position = len('\n'.join(lines[:i]))
                    current_chapter.word_count = len(chapter_content.split())
                    chapters.append(current_chapter)
                
                # Start new chapter
                current_chapter = Chapter(
                    number=chapter_match[0],
                    title=chapter_match[1],
                    content="",
                    start_position=len('\n'.join(lines[:i])),
                    end_position=0,
                    word_count=0
                )
                current_content = []
            else:
                # Add line to current chapter content
                if current_chapter:
                    current_content.append(line)
        
        # Don't forget the last chapter
        if current_chapter:
            chapter_content = '\n'.join(current_content).strip()
            current_chapter.content = chapter_content
            current_chapter.end_position = len(text)
            current_chapter.word_count = len(chapter_content.split())
            chapters.append(current_chapter)
        
        return chapters

    def _is_chapter_heading(self, line: str) -> Optional[Tuple[int, str]]:
        """Check if line is a chapter heading"""
        for pattern in self.chapter_patterns:
            match = re.match(pattern, line, re.IGNORECASE)
            if match:
                try:
                    chapter_num = int(match.group(1))
                    title = match.group(2).strip() if len(match.groups()) > 1 else ""
                    return (chapter_num, title)
                except (ValueError, IndexError):
                    continue
        return None
    
    def clean_text(self, text: str) -> str:
        """Clean text for TTS processing"""
        # Remove excessive whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Fix common formatting issues
        text = re.sub(r'([.!?])\s*([A-Z])', r'\1 \2', text)
        
        # Preserve Australian English spellings
        for us_spelling, au_spelling in self.au_spellings.items():
            text = re.sub(r'\b' + us_spelling + r'\b', au_spelling, text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def chunk_long_text(self, text: str, max_length: int = 4000) -> List[str]:
        """Split long text into chunks at sentence boundaries"""
        if len(text) <= max_length:
            return [text]
        
        sentences = nltk.sent_tokenize(text)
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk + sentence) <= max_length:
                current_chunk += sentence + " "
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                current_chunk = sentence + " "
        
        if current_chunk:
            chunks.append(current_chunk.strip())
        
        return chunks
