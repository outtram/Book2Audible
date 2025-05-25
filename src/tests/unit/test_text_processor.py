"""
Unit tests for text processor
"""
import pytest
from src.core.text_processor import TextProcessor, Chapter

class TestTextProcessor:
    def setup_method(self):
        self.processor = TextProcessor()
    
    def test_chapter_detection_basic(self):
        """Test basic chapter detection"""
        text = """
        Chapter 1: Introduction
        This is the first chapter content.
        
        Chapter 2: Getting Started
        This is the second chapter content.
        """
        
        chapters = self.processor.detect_chapters(text)
        
        assert len(chapters) == 2
        assert chapters[0].number == 1
        assert chapters[0].title == "Introduction"
        assert "first chapter" in chapters[0].content
        
        assert chapters[1].number == 2
        assert chapters[1].title == "Getting Started"
        assert "second chapter" in chapters[1].content
    
    def test_text_cleaning(self):
        """Test text cleaning functionality"""
        dirty_text = "This  has   extra    spaces. And some US spellings like color and organize."
        
        cleaned = self.processor.clean_text(dirty_text)
        
        assert "  " not in cleaned  # No double spaces
        assert "colour" in cleaned  # AU spelling
        assert "organise" in cleaned  # AU spelling
    
    def test_text_chunking(self):
        """Test text chunking at sentence boundaries"""
        long_text = "This is sentence one. " * 100 + "This is the final sentence."
        
        chunks = self.processor.chunk_long_text(long_text, max_length=200)
        
        assert len(chunks) > 1
        for chunk in chunks:
            assert len(chunk) <= 200
            assert chunk.endswith(".")  # Should end with complete sentence
    
    def test_australian_spelling_preservation(self):
        """Test that Australian spellings are preserved"""
        text = "We need to analyse the colour patterns and prioritise the centre location."
        
        cleaned = self.processor.clean_text(text)
        
        assert "analyse" in cleaned
        assert "colour" in cleaned
        assert "prioritise" in cleaned
        assert "centre" in cleaned
        
        # Make sure US spellings aren't there
        assert "analyze" not in cleaned
        assert "color" not in cleaned
        assert "prioritize" not in cleaned
        assert "center" not in cleaned
