"""
Buffer sentence management for TTS context preservation
"""
import numpy as np
from pathlib import Path
from typing import Tuple
import logging

class BufferManager:
    """Manages buffer sentences for TTS context without affecting final output"""
    
    # Use unique nonsense phrases that won't match real text
    BUFFER_START = "Xerxes zigzag buffalo nickel chrome."
    BUFFER_END = "Plasma cookie vertigo umbrella jazz."
    
    def __init__(self, tts_client, audio_processor):
        self.tts_client = tts_client
        self.audio_processor = audio_processor
        self.logger = logging.getLogger(__name__)
        
        # Pre-generate buffer audio to know their lengths
        self._initialize_buffers()
    
    def _initialize_buffers(self):
        """Generate buffer audio once to determine their lengths"""
        try:
            self.logger.info("Initializing buffer sentences...")
            
            # Generate buffer audio
            self.start_buffer_audio = self.tts_client.generate_audio(self.BUFFER_START)
            self.end_buffer_audio = self.tts_client.generate_audio(self.BUFFER_END)
            
            # Convert to numpy arrays to count samples
            start_array = np.frombuffer(self.start_buffer_audio, dtype=np.int16)
            end_array = np.frombuffer(self.end_buffer_audio, dtype=np.int16)
            
            self.start_buffer_samples = len(start_array)
            self.end_buffer_samples = len(end_array)
            
            self.logger.info(f"Buffer lengths: start={self.start_buffer_samples} samples, end={self.end_buffer_samples} samples")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize buffers: {e}")
            # Fallback to no buffers
            self.start_buffer_samples = 0
            self.end_buffer_samples = 0
    
    def add_buffers(self, text: str) -> str:
        """Add buffer sentences to provide context for TTS"""
        return f"{self.BUFFER_START} {text} {self.BUFFER_END}"
    
    def generate_with_buffers(self, text: str) -> bytes:
        """Generate TTS audio with buffers, then trim them out"""
        try:
            # Add buffers to text
            buffered_text = self.add_buffers(text)
            
            self.logger.debug(f"Generating with buffers: {buffered_text[:100]}...")
            
            # Generate audio with buffers
            buffered_audio = self.tts_client.generate_audio(buffered_text)
            
            # Convert to numpy array for precise trimming
            audio_array = np.frombuffer(buffered_audio, dtype=np.int16)
            
            # Trim buffer samples from start and end
            if len(audio_array) > (self.start_buffer_samples + self.end_buffer_samples):
                trimmed_array = audio_array[self.start_buffer_samples:-self.end_buffer_samples]
            else:
                # If audio is shorter than buffers (shouldn't happen), return original
                self.logger.warning("Audio shorter than buffer lengths, returning untrimmed")
                trimmed_array = audio_array
            
            # Convert back to bytes
            trimmed_audio = trimmed_array.tobytes()
            
            self.logger.debug(f"Trimmed audio: {len(buffered_audio)} -> {len(trimmed_audio)} bytes")
            
            return trimmed_audio
            
        except Exception as e:
            self.logger.error(f"Buffer generation failed: {e}")
            # Fallback to no buffers
            return self.tts_client.generate_audio(text)
    
    def is_enabled(self) -> bool:
        """Check if buffer system is properly initialized"""
        return self.start_buffer_samples > 0 and self.end_buffer_samples > 0