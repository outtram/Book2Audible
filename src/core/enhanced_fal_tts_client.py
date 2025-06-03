"""
Enhanced Fal.ai TTS Client with Word-Level Timing Extraction
Extends the existing FalTTSClient to support synchronized audio-text playback
"""
import os
import json
import time
import re
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
import logging

from .fal_tts_client import FalTTSClient
from .chunk_database import ChunkDatabase


class EnhancedFalTTSClient(FalTTSClient):
    """Enhanced TTS client with word timing extraction capabilities"""
    
    def __init__(self):
        super().__init__()
        self.chunk_db = ChunkDatabase()
        self.logger = logging.getLogger(__name__)
        
        # Try to import whisper for word timing extraction
        try:
            import whisper
            self.whisper_model = whisper.load_model("base")
            self.whisper_available = True
            self.logger.info("Whisper model loaded for word timing extraction")
        except ImportError:
            self.whisper_model = None
            self.whisper_available = False
            self.logger.warning("Whisper not available - word timing extraction disabled")
    
    def generate_audio_with_timings(self, text: str, chunk_id: int, 
                                   orpheus_params: Dict[str, Any] = None) -> Tuple[str, List[Dict]]:
        """
        Generate audio and extract word-level timing data
        
        Args:
            text: Text to convert to speech
            chunk_id: Database ID of the chunk
            orpheus_params: TTS parameters (voice, temperature, speed, etc.)
            
        Returns:
            Tuple of (audio_file_path, word_timings)
        """
        # Use default TTS generation first
        audio_path = self.generate_audio(text, orpheus_params or {})
        
        # Extract word timings if Whisper is available
        word_timings = []
        if self.whisper_available and audio_path and Path(audio_path).exists():
            try:
                word_timings = self.extract_word_timings(audio_path, text)
                self.logger.info(f"Extracted {len(word_timings)} word timings for chunk {chunk_id}")
            except Exception as e:
                self.logger.error(f"Failed to extract word timings: {e}")
        
        # Store audio version and timings in database
        if audio_path and chunk_id:
            try:
                audio_version_id = self.chunk_db.create_audio_version(
                    chunk_id=chunk_id,
                    audio_file_path=audio_path,
                    orpheus_params=orpheus_params or {}
                )
                
                if word_timings:
                    self.chunk_db.store_word_timings(audio_version_id, word_timings)
                    
                # Update chunk with Orpheus parameters
                if orpheus_params:
                    self.chunk_db.update_chunk_orpheus_params(
                        chunk_id=chunk_id,
                        temperature=orpheus_params.get('temperature'),
                        voice=orpheus_params.get('voice'),
                        speed=orpheus_params.get('speed')
                    )
                    
            except Exception as e:
                self.logger.error(f"Failed to store audio version data: {e}")
        
        return audio_path, word_timings
    
    def extract_word_timings(self, audio_path: str, original_text: str) -> List[Dict[str, Any]]:
        """
        Extract word-level timestamps using Whisper
        
        Args:
            audio_path: Path to the generated audio file
            original_text: Original text that was converted to speech
            
        Returns:
            List of word timing dictionaries
        """
        if not self.whisper_available:
            return []
        
        try:
            # Transcribe with word-level timestamps
            result = self.whisper_model.transcribe(
                audio_path,
                word_timestamps=True,
                language="en",
                temperature=0.0  # Use deterministic transcription
            )
            
            # Extract word timings from Whisper segments
            whisper_words = []
            for segment in result.get("segments", []):
                for word_info in segment.get("words", []):
                    whisper_words.append({
                        'word': word_info['word'].strip(),
                        'start': word_info['start'],
                        'end': word_info['end'],
                        'confidence': word_info.get('probability', 1.0)
                    })
            
            # Align with original text to get accurate word positions
            aligned_timings = self.align_timings_with_original(whisper_words, original_text)
            
            return aligned_timings
            
        except Exception as e:
            self.logger.error(f"Failed to extract word timings from {audio_path}: {e}")
            return []
    
    def align_timings_with_original(self, whisper_words: List[Dict], original_text: str) -> List[Dict[str, Any]]:
        """
        Align Whisper word timings with the original text
        
        This handles cases where Whisper might transcribe slightly differently
        than the original text, ensuring we maintain accurate character positions.
        """
        # Clean and tokenize original text
        original_words = self.tokenize_text(original_text)
        
        # Create mapping between whisper words and original words
        aligned_timings = []
        whisper_idx = 0
        char_position = 0
        
        for word_idx, original_word in enumerate(original_words):
            # Find character positions in original text
            word_start = original_text.find(original_word['word'], char_position)
            word_end = word_start + len(original_word['word'])
            char_position = word_end
            
            # Try to match with Whisper timing
            timing_data = {
                'word_index': word_idx,
                'word': original_word['word'],
                'char_start': word_start,
                'char_end': word_end,
                'start': 0.0,
                'end': 0.0,
                'confidence': 0.5  # Default confidence when no Whisper match
            }
            
            # Find best matching Whisper word
            if whisper_idx < len(whisper_words):
                whisper_word = whisper_words[whisper_idx]
                
                # Simple fuzzy matching for alignment
                if self.words_match(original_word['word'], whisper_word['word']):
                    timing_data.update({
                        'start': whisper_word['start'],
                        'end': whisper_word['end'],
                        'confidence': whisper_word['confidence']
                    })
                    whisper_idx += 1
                else:
                    # Try to find the word in nearby Whisper results
                    for look_ahead in range(1, min(3, len(whisper_words) - whisper_idx)):
                        if self.words_match(original_word['word'], whisper_words[whisper_idx + look_ahead]['word']):
                            timing_data.update({
                                'start': whisper_words[whisper_idx + look_ahead]['start'],
                                'end': whisper_words[whisper_idx + look_ahead]['end'],
                                'confidence': whisper_words[whisper_idx + look_ahead]['confidence']
                            })
                            whisper_idx += look_ahead + 1
                            break
            
            aligned_timings.append(timing_data)
        
        return aligned_timings
    
    def tokenize_text(self, text: str) -> List[Dict[str, str]]:
        """Tokenize text into words, preserving punctuation context"""
        # Simple word tokenization that maintains punctuation
        words = []
        word_pattern = re.compile(r'\b\w+\b|\S')
        
        for match in word_pattern.finditer(text):
            word = match.group()
            if word.isalpha() or word.isalnum():  # Only include actual words
                words.append({
                    'word': word,
                    'start_pos': match.start(),
                    'end_pos': match.end()
                })
        
        return words
    
    def words_match(self, original: str, transcribed: str, threshold: float = 0.8) -> bool:
        """Check if two words match closely enough for alignment"""
        # Normalize words for comparison
        orig_clean = re.sub(r'[^\w]', '', original.lower())
        trans_clean = re.sub(r'[^\w]', '', transcribed.lower())
        
        if orig_clean == trans_clean:
            return True
        
        # Simple character-based similarity
        if len(orig_clean) == 0 or len(trans_clean) == 0:
            return False
        
        # Calculate simple similarity ratio
        max_len = max(len(orig_clean), len(trans_clean))
        matches = sum(1 for a, b in zip(orig_clean, trans_clean) if a == b)
        similarity = matches / max_len
        
        return similarity >= threshold
    
    def generate_chapter_word_mapping(self, chapter_id: int) -> List[Dict[str, Any]]:
        """
        Generate comprehensive word mapping for a chapter
        Combines all chunk word timings into chapter-level mapping
        """
        chunks = self.chunk_db.get_chunks_by_chapter(chapter_id)
        chapter_words = []
        current_audio_time = 0.0
        word_index = 0
        
        for chunk in sorted(chunks, key=lambda x: x.chunk_number):
            # Get active audio version for this chunk
            audio_version = self.chunk_db.get_active_audio_version(chunk.id)
            if not audio_version:
                continue
            
            # Get word timings for this audio version
            word_timings = self.chunk_db.get_word_timings(audio_version['id'])
            
            # Adjust timings to chapter-level timeline
            for timing in word_timings:
                chapter_words.append({
                    'word_index': word_index,
                    'word': timing['word'],
                    'chunk_id': chunk.id,
                    'char_start': chunk.position_start + timing.get('char_start', 0),
                    'char_end': chunk.position_start + timing.get('char_end', 0),
                    'audio_start_time': current_audio_time + timing['start'],
                    'audio_end_time': current_audio_time + timing['end']
                })
                word_index += 1
            
            # Update audio timeline for next chunk
            if audio_version.get('duration_seconds'):
                current_audio_time += audio_version['duration_seconds']
        
        # Store chapter word mapping
        if chapter_words:
            self.chunk_db.store_chapter_words(chapter_id, chapter_words)
        
        return chapter_words
    
    def reprocess_chunk_with_params(self, chunk_id: int, new_params: Dict[str, Any]) -> Tuple[str, List[Dict]]:
        """
        Reprocess a chunk with new Orpheus parameters
        
        Args:
            chunk_id: ID of chunk to reprocess
            new_params: New TTS parameters to use
            
        Returns:
            Tuple of (audio_file_path, word_timings)
        """
        chunk = self.chunk_db.get_chunk(chunk_id)
        if not chunk:
            raise ValueError(f"Chunk {chunk_id} not found")
        
        self.logger.info(f"Reprocessing chunk {chunk_id} with new parameters: {new_params}")
        
        # Generate new audio with updated parameters
        audio_path, word_timings = self.generate_audio_with_timings(
            text=chunk.cleaned_text,
            chunk_id=chunk_id,
            orpheus_params=new_params
        )
        
        # Update chunk status
        self.chunk_db.update_chunk_status(
            chunk_id=chunk_id,
            status='completed',
            audio_file_path=audio_path,
            processing_time=time.time()  # Should track actual processing time
        )
        
        return audio_path, word_timings