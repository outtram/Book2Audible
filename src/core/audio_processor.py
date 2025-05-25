"""
Audio processing for seamless WAV stitching and quality control
"""
import wave
import struct
import io
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging
from pydub import AudioSegment
from pydub.silence import split_on_silence
import numpy as np

from .config import config

class AudioProcessor:
    """Handles audio stitching, normalization, and quality control"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.sample_rate = config.tts_settings.get("sample_rate", 44100)
        self.bit_depth = config.tts_settings.get("bit_depth", 16)
        self.channels = config.tts_settings.get("channels", 2)
        self.fade_duration = config.tts_settings.get("fade_duration", 50)
        self.normalize_audio = config.tts_settings.get("normalize_audio", True)
    
    def stitch_audio_chunks(self, audio_chunks: List[bytes]) -> bytes:
        """Stitch multiple audio chunks into seamless audio"""
        if not audio_chunks:
            raise ValueError("No audio chunks provided")
        
        if len(audio_chunks) == 1:
            return audio_chunks[0]
        
        self.logger.info(f"Stitching {len(audio_chunks)} audio chunks")
        
        # Convert bytes to AudioSegment objects
        audio_segments = []
        for i, chunk in enumerate(audio_chunks):
            try:
                # Create temporary file-like object
                segment = AudioSegment.from_wav(io.BytesIO(chunk))
                
                # Apply fade in/out to prevent clicks
                if i > 0:  # Fade in for all but first chunk
                    segment = segment.fade_in(self.fade_duration)
                if i < len(audio_chunks) - 1:  # Fade out for all but last chunk
                    segment = segment.fade_out(self.fade_duration)
                    
                audio_segments.append(segment)
                self.logger.debug(f"Processed chunk {i + 1}: {len(segment)}ms")
                
            except Exception as e:
                self.logger.error(f"Failed to process audio chunk {i + 1}: {e}")
                raise
        
        # Combine all segments
        combined_audio = AudioSegment.empty()
        for segment in audio_segments:
            combined_audio += segment
        
        # Normalize if requested
        if self.normalize_audio:
            combined_audio = combined_audio.normalize()
            
        self.logger.info(f"Audio stitching completed. Final length: {len(combined_audio)}ms")
        
        # Export to bytes
        return self._export_to_bytes(combined_audio)

    def _export_to_bytes(self, audio: AudioSegment) -> bytes:
        """Export AudioSegment to WAV bytes"""
        buffer = io.BytesIO()
        audio.export(buffer, format="wav")
        return buffer.getvalue()
    
    def save_wav_file(self, audio_data: bytes, output_path: Path) -> None:
        """Save audio data to WAV file"""
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Check if audio_data is raw PCM or already a WAV file
            if not audio_data.startswith(b'RIFF'):
                # Raw PCM data - need to add WAV header
                audio_data = self._add_wav_header(audio_data)
            
            with open(output_path, 'wb') as f:
                f.write(audio_data)
            self.logger.info(f"Audio saved to: {output_path}")
        except Exception as e:
            self.logger.error(f"Failed to save audio file: {e}")
            raise
    
    def _add_wav_header(self, pcm_data: bytes) -> bytes:
        """Add WAV header to raw PCM data"""
        # PCM data length
        data_length = len(pcm_data)
        
        # WAV file parameters
        sample_rate = self.sample_rate
        bits_per_sample = self.bit_depth
        channels = self.channels
        byte_rate = sample_rate * channels * bits_per_sample // 8
        block_align = channels * bits_per_sample // 8
        
        # Create WAV header
        header = bytearray()
        
        # RIFF header
        header.extend(b'RIFF')
        header.extend((36 + data_length).to_bytes(4, 'little'))  # File size - 8
        header.extend(b'WAVE')
        
        # fmt chunk
        header.extend(b'fmt ')
        header.extend((16).to_bytes(4, 'little'))  # fmt chunk size
        header.extend((1).to_bytes(2, 'little'))   # PCM format
        header.extend(channels.to_bytes(2, 'little'))
        header.extend(sample_rate.to_bytes(4, 'little'))
        header.extend(byte_rate.to_bytes(4, 'little'))
        header.extend(block_align.to_bytes(2, 'little'))
        header.extend(bits_per_sample.to_bytes(2, 'little'))
        
        # data chunk
        header.extend(b'data')
        header.extend(data_length.to_bytes(4, 'little'))
        
        # Combine header and data
        return bytes(header) + pcm_data
    
    def validate_audio_quality(self, audio_path: Path) -> Dict[str, Any]:
        """Validate audio file quality parameters"""
        try:
            audio = AudioSegment.from_wav(str(audio_path))
            
            quality_info = {
                "sample_rate": audio.frame_rate,
                "channels": audio.channels,
                "duration_ms": len(audio),
                "bit_depth": audio.sample_width * 8,
                "file_size": audio_path.stat().st_size,
                "meets_requirements": True
            }
            
            # Check if meets requirements
            if audio.frame_rate != self.sample_rate:
                quality_info["meets_requirements"] = False
                self.logger.warning(f"Sample rate mismatch: {audio.frame_rate} vs {self.sample_rate}")
            
            if audio.channels != self.channels:
                quality_info["meets_requirements"] = False
                self.logger.warning(f"Channel count mismatch: {audio.channels} vs {self.channels}")
                
            return quality_info
            
        except Exception as e:
            self.logger.error(f"Audio validation failed: {e}")
            return {"meets_requirements": False, "error": str(e)}
