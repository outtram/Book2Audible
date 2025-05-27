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
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab')
    
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
        import logging
        self.logger = logging.getLogger(__name__)
        
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
        
        # If no chapters were detected, treat entire text as single chapter
        if not chapters and text.strip():
            # Use first line as title if available, otherwise use filename-based title
            lines = text.strip().split('\n')
            first_line = lines[0].strip() if lines else "Content"
            
            # If first line looks like a title (short and not ending with period), use it
            if len(first_line) < 100 and not first_line.endswith('.'):
                title = first_line
                # Include the title in the content so it gets read aloud
                content = text.strip()
            else:
                title = "Audio Content"
                content = text.strip()
            
            single_chapter = Chapter(
                number=1,
                title=title,
                content=content,
                start_position=0,
                end_position=len(text),
                word_count=len(content.split())
            )
            chapters.append(single_chapter)
        
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
        """Aggressively clean text for TTS processing to prevent hallucinations"""
        # Normalize quotes - replace smart quotes with regular quotes
        text = re.sub(r'[""''„"«»]', '"', text)
        
        # Normalize dashes - replace em-dashes and en-dashes with hyphens
        text = re.sub(r'[–—]', '-', text)
        
        # Fix ellipsis - replace multiple dots with single period
        text = re.sub(r'\.{2,}', '.', text)
        
        # Remove orphaned punctuation and fix spacing
        text = re.sub(r'\s+([,.!?;:])', r'\1', text)  # Remove space before punctuation
        text = re.sub(r'([.!?])\s*([A-Z])', r'\1 \2', text)  # Ensure space after sentence end
        
        # Normalize whitespace - remove double spaces and normalize to single spaces
        text = re.sub(r'\s+', ' ', text)
        
        # Remove special characters that confuse TTS
        text = re.sub(r'[^\w\s.,!?;:()\'-]', '', text)
        
        # Fix common formatting issues
        text = re.sub(r'\(\s+', '(', text)  # Fix "( text" to "(text"
        text = re.sub(r'\s+\)', ')', text)  # Fix "text )" to "text)"
        
        # Preserve Australian English spellings
        for us_spelling, au_spelling in self.au_spellings.items():
            text = re.sub(r'\b' + us_spelling + r'\b', au_spelling, text, flags=re.IGNORECASE)
        
        # Final cleanup
        text = text.strip()
        
        # Ensure text ends with proper punctuation
        if text and not text[-1] in '.!?':
            text += '.'
            
        return text
    
    def chunk_long_text(self, text: str, max_length: int = 150) -> List[str]:
        """Split text at sentence boundaries ONLY - never mid-sentence to prevent hallucinations"""
        if len(text) <= max_length:
            return [text]
        
        sentences = nltk.sent_tokenize(text)
        chunks = []
        current_chunk = ""
        
        for i, sentence in enumerate(sentences):
            # Always keep complete sentences together
            if not current_chunk:
                # Starting new chunk
                current_chunk = sentence
            elif len(current_chunk + " " + sentence) <= max_length:
                # Add sentence to current chunk
                current_chunk += " " + sentence
            else:
                # Current chunk is full, save it and start new one
                chunks.append(current_chunk.strip())
                current_chunk = sentence
        
        # Don't forget the last chunk
        if current_chunk.strip():
            chunks.append(current_chunk.strip())
        
        # If any single sentence is longer than max_length, keep it as its own chunk
        # (Don't split mid-sentence as this causes hallucinations)
        final_chunks = []
        for chunk in chunks:
            if len(chunk) > max_length:
                # Log warning but keep the long sentence intact
                self.logger.warning(f"Sentence too long ({len(chunk)} chars) but keeping intact to prevent hallucinations")
            final_chunks.append(chunk)
        
        return final_chunks
    
    def _split_long_sentence(self, sentence: str, max_length: int) -> List[str]:
        """Split a very long sentence at natural break points"""
        if len(sentence) <= max_length:
            return [sentence]
        
        # Try to split at natural breakpoints: comma, semicolon, dash, parentheses
        break_patterns = [', ', '; ', ' - ', ' – ', ' (', ') ']
        
        for pattern in break_patterns:
            if pattern in sentence:
                parts = sentence.split(pattern)
                chunks = []
                current = ""
                
                for i, part in enumerate(parts):
                    # Restore the break pattern (except for last part)
                    restored_part = part + (pattern if i < len(parts) - 1 else "")
                    
                    if len(current + restored_part) <= max_length:
                        current += restored_part
                    else:
                        if current:
                            chunks.append(current.strip())
                        current = restored_part
                
                if current:
                    chunks.append(current.strip())
                
                # If we successfully split, return the chunks
                if len(chunks) > 1:
                    return chunks
        
        # If no natural breakpoints, split by words as last resort
        words = sentence.split()
        chunks = []
        current = ""
        
        for word in words:
            if len(current + word + " ") <= max_length:
                current += word + " "
            else:
                if current:
                    chunks.append(current.strip())
                current = word + " "
        
        if current:
            chunks.append(current.strip())
        
        return chunks
