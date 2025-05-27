"""
Fal.ai TTS Client for Orpheus model integration
"""
import os
import requests
import time
import logging
from typing import List, Optional, Dict, Any
from pathlib import Path

try:
    import fal_client
except ImportError:
    fal_client = None

from .config import config

class FalTTSClient:
    """Client for Fal.ai Orpheus TTS API"""
    
    def __init__(self):
        if fal_client is None:
            raise ImportError("fal-client not installed. Run: pip install fal-client")
            
        self.api_key = os.getenv('FAL_KEY') or config.fal_config.get("api_key")
        self.model_id = "fal-ai/orpheus-tts"
        self.timeout = config.fal_config.get("timeout", 120)
        self.retry_attempts = config.fal_config.get("retry_attempts", 3)
        self.rate_limit = config.fal_config.get("rate_limit_per_minute", 120)  # Higher limit for Fal.ai
        
        self.logger = logging.getLogger(__name__)
        
        # Validate configuration
        if not self.api_key or self.api_key.startswith("${"):
            raise ValueError("Fal.ai API key not configured. Set FAL_KEY environment variable.")
        
        # Set the API key for fal_client
        os.environ['FAL_KEY'] = self.api_key
        
        self.logger.info("Fal.ai TTS client initialized")
    
    def generate_audio(self, text: str, voice: str = None) -> bytes:
        """Generate audio for a single text chunk"""
        if not text.strip():
            raise ValueError("Text cannot be empty")
        
        voice = voice or config.tts_settings.get("voice", "tara")
        
        # Fal.ai API parameters
        arguments = {
            "text": text,
            "voice": voice,
            "temperature": config.tts_settings.get("temperature", 0.7),
            "repetition_penalty": config.tts_settings.get("repetition_penalty", 1.2)
        }
        
        for attempt in range(self.retry_attempts):
            try:
                self.logger.info(f"Generating audio for text chunk (attempt {attempt + 1}/{self.retry_attempts})")
                self.logger.debug(f"Text length: {len(text)} characters")
                self.logger.debug(f"Voice: {voice}")
                
                # Dynamic timeout based on text length
                dynamic_timeout = max(self.timeout, len(text) * 0.3)  # 0.3s per character for Fal.ai
                dynamic_timeout = min(dynamic_timeout, 300)  # Cap at 5 minutes
                
                self.logger.debug(f"Using timeout: {dynamic_timeout}s for {len(text)} character text")
                
                # Call Fal.ai API
                start_time = time.time()
                result = fal_client.subscribe(
                    self.model_id,
                    arguments=arguments,
                    timeout=dynamic_timeout
                )
                
                generation_time = time.time() - start_time
                self.logger.info(f"Audio generation completed in {generation_time:.1f}s")
                
                # Check if result contains audio URL
                if not result or 'audio' not in result:
                    raise Exception(f"Invalid response from Fal.ai API: {result}")
                
                audio_url = result['audio']
                self.logger.debug(f"Audio URL received: {audio_url}")
                
                # Download the audio file
                download_start = time.time()
                audio_response = requests.get(audio_url, timeout=60)
                audio_response.raise_for_status()
                
                download_time = time.time() - download_start
                self.logger.info(f"Audio download completed in {download_time:.1f}s")
                self.logger.debug(f"Audio file size: {len(audio_response.content)} bytes")
                
                # Validate audio content
                if len(audio_response.content) < 1000:  # Less than 1KB is suspicious
                    self.logger.warning(f"Small audio file received: {len(audio_response.content)} bytes")
                
                return audio_response.content
                
            except Exception as e:
                error_msg = str(e)
                self.logger.warning(f"Attempt {attempt + 1} failed: {error_msg}")
                
                # Handle different types of errors
                if "timeout" in error_msg.lower():
                    if attempt < self.retry_attempts - 1:
                        backoff_time = (2 ** attempt) * 2  # Exponential backoff
                        self.logger.info(f"Timeout occurred, retrying in {backoff_time} seconds...")
                        time.sleep(backoff_time)
                        continue
                    else:
                        raise TimeoutError(f"Fal.ai TTS generation timed out after {self.retry_attempts} attempts")
                        
                elif "rate limit" in error_msg.lower() or "429" in error_msg:
                    if attempt < self.retry_attempts - 1:
                        wait_time = (2 ** attempt) * 10  # Longer wait for rate limits
                        self.logger.warning(f"Rate limit hit, waiting {wait_time} seconds...")
                        time.sleep(wait_time)
                        continue
                    else:
                        raise Exception(f"Rate limit exceeded after {self.retry_attempts} attempts")
                        
                elif attempt == self.retry_attempts - 1:
                    # Final attempt failed
                    raise Exception(f"Fal.ai TTS generation failed after {self.retry_attempts} attempts: {error_msg}")
                else:
                    # Other errors - wait and retry
                    backoff_time = 2 ** attempt
                    self.logger.info(f"Retrying in {backoff_time} seconds...")
                    time.sleep(backoff_time)
        
        raise Exception("All retry attempts failed")
    
    def batch_generate(self, text_chunks: List[str], voice: str = None) -> List[bytes]:
        """Generate audio for multiple text chunks"""
        self.logger.info(f"Starting batch generation for {len(text_chunks)} chunks")
        audio_chunks = []
        
        for i, text_chunk in enumerate(text_chunks):
            self.logger.info(f"Processing chunk {i + 1}/{len(text_chunks)}")
            audio_data = self.generate_audio(text_chunk, voice)
            audio_chunks.append(audio_data)
            
            # Rate limiting - Fal.ai has higher limits but still be respectful
            if i < len(text_chunks) - 1:  # Don't sleep after last chunk
                sleep_time = max(60 / self.rate_limit, 0.5)  # Minimum 0.5s between requests
                time.sleep(sleep_time)
        
        self.logger.info("Batch generation completed")
        return audio_chunks
    
    def test_connection(self) -> bool:
        """Test API connection with a simple request"""
        try:
            self.logger.info("Testing Fal.ai API connection...")
            test_audio = self.generate_audio("Test connection.", "tara")
            
            if len(test_audio) > 1000:  # Valid audio should be larger than 1KB
                self.logger.info("✅ Fal.ai API connection test successful")
                return True
            else:
                self.logger.error("❌ Fal.ai API test failed: audio too small")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Fal.ai API connection test failed: {e}")
            return False
    
    def get_available_voices(self) -> List[str]:
        """Get list of available voices"""
        # From Fal.ai documentation
        return ["tara", "leah", "jess", "leo", "dan", "mia", "zac", "zoe"]
    
    def calculate_cost(self, character_count: int) -> float:
        """Calculate estimated cost for character count"""
        # Fal.ai pricing: $0.05 per 1000 characters
        return (character_count / 1000) * 0.05
    
    def get_provider_info(self) -> Dict[str, Any]:
        """Get information about this TTS provider"""
        return {
            "provider": "Fal.ai",
            "model": "Orpheus TTS",
            "pricing": "$0.05 per 1000 characters",
            "voices": self.get_available_voices(),
            "features": [
                "High-quality speech generation",
                "Emotional expression support",
                "Real-time performance",
                "Multiple voice options",
                "Llama-based Speech-LLM"
            ],
            "emotional_tags": ["<laugh>", "<chuckle>", "<sigh>", "<cough>", "<sniffle>", "<groan>", "<yawn>", "<gasp>"],
            "api_limits": {
                "max_characters_per_request": 10000,  # Estimated
                "rate_limit_per_minute": self.rate_limit
            }
        }