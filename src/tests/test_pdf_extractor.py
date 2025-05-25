#!/usr/bin/env python3
"""
Test PDF Extraction functionality
"""
# import pytest
import tempfile
from pathlib import Path
import sys

# Add src to path
sys.path.append(str(Path(__file__).parent.parent))

from core.pdf_extractor import PDFExtractor, ChapterInfo

class TestPDFExtractor:
    """Test PDF extraction functionality"""
    
    def test_chapter_header_detection(self):
        """Test chapter header pattern matching"""
        extractor = PDFExtractor()
        
        # Test positive cases
        assert extractor._is_chapter_header("Chapter 1")
        assert extractor._is_chapter_header("Chapter 10")
        assert extractor._is_chapter_header("Introduction")
        assert extractor._is_chapter_header("Contents")
        assert extractor._is_chapter_header("About the Author")
        assert extractor._is_chapter_header("References")
        
        # Test negative cases
        assert not extractor._is_chapter_header("This is regular text")
        assert not extractor._is_chapter_header("Chapter content here")
        assert not extractor._is_chapter_header("Some random line")
    
    def test_header_footer_detection(self):
        """Test header/footer pattern matching"""
        extractor = PDFExtractor()
        
        # Test positive cases (should be removed)
        assert extractor._is_header_footer("Using the Brain Science of ADHD as a Guide for Neuro-affirming Practice")
        assert extractor._is_header_footer("42")  # Page number
        assert extractor._is_header_footer("  123  ")  # Page number with spaces
        assert extractor._is_header_footer("Chapter 5 Some Title")
        
        # Test negative cases (should be kept)
        assert not extractor._is_header_footer("This is regular content")
        assert not extractor._is_header_footer("Chapter 5 content starts here")
    
    def test_filename_generation(self):
        """Test filename generation from chapter titles"""
        extractor = PDFExtractor()
        
        # Test specific chapter cases
        assert extractor._generate_filename("Contents", 0) == "contents"
        assert extractor._generate_filename("About the Author", 1) == "about_the_author"
        assert extractor._generate_filename("Introduction", 2) == "introduction"
        assert extractor._generate_filename("Chapter 1", 3) == "chapter_01"
        assert extractor._generate_filename("Chapter 10", 4) == "chapter_10"
        assert extractor._generate_filename("References", 5) == "references"
        
        # Test fallback case
        result = extractor._generate_filename("Some Random Title", 6)
        assert result.startswith("section_07_")
    
    def test_content_cleaning(self):
        """Test content cleaning functionality"""
        extractor = PDFExtractor()
        
        # Test content with headers/footers mixed in
        content_lines = [
            "This is good content",
            "42",  # Page number - should be removed
            "More good content here",
            "Using the Brain Science of ADHD as a Guide for Neuro-affirming Practice",  # Header - should be removed
            "Final line of content"
        ]
        
        cleaned = extractor._clean_content(content_lines)
        
        # Should only contain the good content
        expected_lines = [
            "This is good content",
            "More good content here", 
            "Final line of content"
        ]
        expected = '\n'.join(expected_lines)
        
        assert cleaned == expected

if __name__ == "__main__":
    test_instance = TestPDFExtractor()
    
    print("🧪 Running PDF Extractor Tests...")
    
    try:
        test_instance.test_chapter_header_detection()
        print("✅ Chapter header detection test passed")
    except Exception as e:
        print(f"❌ Chapter header detection test failed: {e}")
    
    try:
        test_instance.test_header_footer_detection()
        print("✅ Header/footer detection test passed")
    except Exception as e:
        print(f"❌ Header/footer detection test failed: {e}")
    
    try:
        test_instance.test_filename_generation()
        print("✅ Filename generation test passed")
    except Exception as e:
        print(f"❌ Filename generation test failed: {e}")
    
    try:
        test_instance.test_content_cleaning()
        print("✅ Content cleaning test passed")
    except Exception as e:
        print(f"❌ Content cleaning test failed: {e}")
    
    print("🎉 All tests completed!")
