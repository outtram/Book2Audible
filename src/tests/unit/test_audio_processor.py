"""
Unit tests for audio processor
"""
import pytest
import io
from unittest.mock import Mock, patch
from src.core.audio_processor import AudioProcessor

class TestAudioProcessor:
    def setup_method(self):
        self.processor = AudioProcessor()
    
    def test_audio_processor_initialization(self):
        """Test audio processor initializes with correct settings"""
        assert self.processor.sample_rate == 44100
        assert self.processor.bit_depth == 16
        assert self.processor.channels == 2
        assert self.processor.fade_duration == 50
    
    @patch('src.core.audio_processor.AudioSegment')
    def test_stitch_single_chunk(self, mock_audio_segment):
        """Test stitching with single audio chunk"""
        single_chunk = [b'fake_audio_data']
        
        result = self.processor.stitch_audio_chunks(single_chunk)
        
        assert result == b'fake_audio_data'
    
    def test_empty_chunks_raises_error(self):
        """Test that empty chunks list raises ValueError"""
        with pytest.raises(ValueError, match="No audio chunks provided"):
            self.processor.stitch_audio_chunks([])
    
    @patch('src.core.audio_processor.AudioSegment')
    def test_export_to_bytes(self, mock_audio_segment):
        """Test audio export to bytes"""
        mock_audio = Mock()
        mock_buffer = io.BytesIO(b'test_audio_bytes')
        
        with patch('io.BytesIO', return_value=mock_buffer):
            result = self.processor._export_to_bytes(mock_audio)
            
        mock_audio.export.assert_called_once_with(mock_buffer, format="wav")
