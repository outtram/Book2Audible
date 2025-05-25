"""
Integration tests for end-to-end processing
"""
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

from src.core.processor import Book2AudioProcessor

class TestEndToEndProcessing:
    def setup_method(self):
        self.temp_dir = Path(tempfile.mkdtemp())
        self.sample_book_content = """
        Chapter 1: Introduction
        This is a sample book chapter about ADHD and how to prioritise tasks.
        We need to analyse different approaches and organise our thoughts.
        
        Chapter 2: Strategies
        Here are some colour-coded strategies for better organisation.
        The centre of our approach should be recognising patterns.
        """
    
    def teardown_method(self):
        """Clean up temp files"""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)
    
    def test_sample_book_processing(self):
        """Test processing a sample book with mocked TTS"""
        # Create sample input file
        input_file = self.temp_dir / "sample_book.txt"
        input_file.write_text(self.sample_book_content)
        
        # Mock the TTS client to avoid actual API calls
        with patch('src.core.processor.BaseTenTTSClient') as mock_tts_class:
            mock_tts = Mock()
            mock_tts.batch_generate.return_value = [b'fake_audio_data']
            mock_tts_class.return_value = mock_tts
            
            # Mock audio processor
            with patch('src.core.processor.AudioProcessor') as mock_audio_class:
                mock_audio = Mock()
                mock_audio.stitch_audio_chunks.return_value = b'final_audio'
                mock_audio.validate_audio_quality.return_value = {'meets_requirements': True}
                mock_audio_class.return_value = mock_audio
                
                # Run processing
                processor = Book2AudioProcessor("INFO")
                summary = processor.process_book(input_file, self.temp_dir)
                
                # Verify results
                assert summary['total_chapters'] == 2
                assert summary['successful_chapters'] == 2
                assert summary['failed_chapters'] == 0
    
    def test_chapter_detection_accuracy(self):
        """Test that chapters are detected correctly"""
        from src.core.text_processor import TextProcessor
        
        processor = TextProcessor()
        chapters = processor.detect_chapters(self.sample_book_content)
        
        assert len(chapters) == 2
        assert chapters[0].title == "Introduction"
        assert chapters[1].title == "Strategies"
        
        # Verify Australian spellings are preserved
        assert "prioritise" in chapters[0].content
        assert "analyse" in chapters[0].content
        assert "colour" in chapters[1].content
        assert "organisation" in chapters[1].content
