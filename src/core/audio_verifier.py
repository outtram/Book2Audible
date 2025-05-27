"""
Audio content verification using speech-to-text transcription
"""
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
import difflib
import re
from dataclasses import dataclass

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False

from .config import config

@dataclass
class VerificationResult:
    """Results of audio content verification"""
    original_text: str
    transcribed_text: str
    accuracy_score: float
    word_error_rate: float
    character_error_rate: float
    missing_words: list
    extra_words: list
    is_verified: bool
    error_message: Optional[str] = None

class AudioVerifier:
    """Verifies audio content matches original text using speech-to-text"""
    
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.model = None
        self.verification_enabled = config.tts_settings.get("enable_verification", True)
        self.accuracy_threshold = config.tts_settings.get("verification_threshold", 0.85)
        
        if self.verification_enabled and WHISPER_AVAILABLE:
            self._initialize_model()
        elif self.verification_enabled and not WHISPER_AVAILABLE:
            self.logger.warning("Audio verification enabled but faster-whisper not installed")
    
    def _initialize_model(self):
        """Initialize Whisper model optimized for M1 Mac"""
        try:
            # Use small model for balance of speed/accuracy
            model_size = config.tts_settings.get("whisper_model_size", "small")
            
            self.logger.info(f"Loading Whisper model: {model_size}")
            self.model = WhisperModel(
                model_size, 
                device="auto",  # Automatically detects M1/GPU
                compute_type="int8"  # Optimized for M1
            )
            self.logger.info("Whisper model loaded successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to load Whisper model: {e}")
            self.model = None
    
    def verify_audio_content(self, audio_path: Path, original_text: str) -> VerificationResult:
        """Verify that audio content matches original text"""
        
        if not self.verification_enabled:
            return VerificationResult(
                original_text=original_text,
                transcribed_text="",
                accuracy_score=1.0,
                word_error_rate=0.0,
                character_error_rate=0.0,
                missing_words=[],
                extra_words=[],
                is_verified=True,
                error_message="Verification disabled"
            )
        
        if not WHISPER_AVAILABLE:
            return VerificationResult(
                original_text=original_text,
                transcribed_text="",
                accuracy_score=0.0,
                word_error_rate=1.0,
                character_error_rate=1.0,
                missing_words=[],
                extra_words=[],
                is_verified=False,
                error_message="faster-whisper not installed"
            )
        
        if not self.model:
            return VerificationResult(
                original_text=original_text,
                transcribed_text="",
                accuracy_score=0.0,
                word_error_rate=1.0,
                character_error_rate=1.0,
                missing_words=[],
                extra_words=[],
                is_verified=False,
                error_message="Whisper model not loaded"
            )
        
        try:
            # Transcribe audio
            self.logger.info(f"Transcribing audio: {audio_path}")
            transcribed_text = self._transcribe_audio(audio_path)
            
            # Compare texts
            comparison_result = self._compare_texts(original_text, transcribed_text)
            
            # Determine if verification passed
            is_verified = comparison_result.accuracy_score >= self.accuracy_threshold
            
            if is_verified:
                self.logger.info(f"Audio verification PASSED: {comparison_result.accuracy_score:.2%} accuracy")
            else:
                self.logger.warning(f"Audio verification FAILED: {comparison_result.accuracy_score:.2%} accuracy (threshold: {self.accuracy_threshold:.2%})")
            
            return VerificationResult(
                original_text=original_text,
                transcribed_text=transcribed_text,
                accuracy_score=comparison_result.accuracy_score,
                word_error_rate=comparison_result.word_error_rate,
                character_error_rate=comparison_result.character_error_rate,
                missing_words=comparison_result.missing_words,
                extra_words=comparison_result.extra_words,
                is_verified=is_verified
            )
            
        except Exception as e:
            self.logger.error(f"Audio verification failed: {e}")
            return VerificationResult(
                original_text=original_text,
                transcribed_text="",
                accuracy_score=0.0,
                word_error_rate=1.0,
                character_error_rate=1.0,
                missing_words=[],
                extra_words=[],
                is_verified=False,
                error_message=str(e)
            )
    
    def _transcribe_audio(self, audio_path: Path) -> str:
        """Transcribe audio file to text using Whisper"""
        try:
            # Transcribe with Australian English language hint
            segments, info = self.model.transcribe(
                str(audio_path),
                language="en",  # English
                task="transcribe",
                beam_size=5,
                best_of=5,
                temperature=0.0,  # More deterministic
                condition_on_previous_text=False
            )
            
            # Combine all segments
            transcribed_text = " ".join([segment.text.strip() for segment in segments])
            
            self.logger.debug(f"Transcription completed: {len(transcribed_text)} characters")
            return transcribed_text.strip()
            
        except Exception as e:
            self.logger.error(f"Transcription failed: {e}")
            raise
    
    def _compare_texts(self, original: str, transcribed: str) -> 'ComparisonResult':
        """Compare original and transcribed text for accuracy"""
        
        # Normalize texts for comparison
        orig_normalized = self._normalize_text(original)
        trans_normalized = self._normalize_text(transcribed)
        
        # Split into words
        orig_words = orig_normalized.split()
        trans_words = trans_normalized.split()
        
        # Calculate similarity using difflib
        similarity = difflib.SequenceMatcher(None, orig_normalized, trans_normalized).ratio()
        
        # Calculate word-level differences
        word_diffs = list(difflib.unified_diff(orig_words, trans_words, lineterm=''))
        
        # Count errors
        missing_words = []
        extra_words = []
        
        for line in word_diffs:
            if line.startswith('- '):
                missing_words.append(line[2:])
            elif line.startswith('+ '):
                extra_words.append(line[2:])
        
        # Calculate error rates
        word_error_rate = len(missing_words + extra_words) / max(len(orig_words), 1)
        char_error_rate = 1.0 - similarity
        
        return ComparisonResult(
            accuracy_score=similarity,
            word_error_rate=word_error_rate,
            character_error_rate=char_error_rate,
            missing_words=missing_words,
            extra_words=extra_words
        )
    
    def _normalize_text(self, text: str) -> str:
        """Normalize text for comparison"""
        # Convert to lowercase
        text = text.lower()
        
        # Remove punctuation and extra whitespace
        text = re.sub(r'[^\w\s]', '', text)
        text = re.sub(r'\s+', ' ', text)
        
        # Handle common transcription variations
        replacements = {
            'centre': 'center',  # AU vs US spelling variations
            'colour': 'color',
            'organise': 'organize',
            'recognise': 'recognize',
            'analyse': 'analyze',
            'prioritise': 'prioritize'
        }
        
        for aus_spelling, us_spelling in replacements.items():
            text = text.replace(aus_spelling, us_spelling)
            text = text.replace(us_spelling, us_spelling)  # Normalize to US for comparison
        
        return text.strip()

@dataclass
class ComparisonResult:
    """Results of text comparison"""
    accuracy_score: float
    word_error_rate: float
    character_error_rate: float
    missing_words: list
    extra_words: list