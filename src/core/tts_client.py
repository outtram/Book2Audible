"""
Baseten TTS Client for Orpheus model integration
"""
import requests
import time
import json
import base64
from typing import List, Optional, Dict, Any
from pathlib import Path
import logging

from .config import config

class BaseTenTTSClient:
    """Client for Baseten Orpheus TTS API"""
    
    def __init__(self):
        self.api_key = config.baseten_api_key
        self.model_id = config.model_id
        self.base_url = config.baseten_config.get("base_url")
        self.timeout = config.baseten_config.get("timeout", 60)
        self.retry_attempts = config.baseten_config.get("retry_attempts", 3)
        self.rate_limit = config.baseten_config.get("rate_limit_per_minute", 60)
        
        self.logger = logging.getLogger(__name__)
        
        # Validate configuration
        if not self.api_key or self.api_key.startswith("${"):
            raise ValueError("Baseten API key not configured. Set BASETEN_API_KEY environment variable.")
    
    def generate_audio(self, text: str, voice: str = None) -> bytes:
        """Generate audio for a single text chunk"""
        if not text.strip():
            raise ValueError("Text cannot be empty")
        
        voice = voice or config.tts_settings.get("voice", "tara")
        
        # Match exact Baseten API format with LLM generation parameters
        payload = {
            "voice": voice,
            "prompt": text,
            "temperature": config.tts_settings.get("temperature", 0.7),
            "top_p": config.tts_settings.get("top_p", 0.9),
            "repetition_penalty": config.tts_settings.get("repetition_penalty", 1.1)
        }
        
        headers = {
            "Authorization": f"Api-Key {self.api_key}",
            "Content-Type": "application/json"
        }
        
        for attempt in range(self.retry_attempts):
            try:
                self.logger.info(f"Generating audio for text chunk (attempt {attempt + 1}/{self.retry_attempts})")
                self.logger.debug(f"Text length: {len(text)} characters")
                
                # Dynamic timeout based on text length
                dynamic_timeout = max(self.timeout, len(text) * 0.5)  # 0.5 seconds per character minimum
                dynamic_timeout = min(dynamic_timeout, 300)  # Cap at 5 minutes
                
                self.logger.debug(f"Using timeout: {dynamic_timeout}s for {len(text)} character text")
                
                response = requests.post(
                    self.base_url,
                    json=payload,
                    headers=headers,
                    timeout=dynamic_timeout
                )
                
                if response.status_code == 200:
                    self.logger.info("Audio generation successful")
                    self.logger.debug(f"Response content type: {response.headers.get('content-type', 'unknown')}")
                    self.logger.debug(f"Response size: {len(response.content)} bytes")
                    
                    # Check if response is JSON (common with some APIs)
                    content_type = response.headers.get('content-type', '').lower()
                    if 'application/json' in content_type:
                        try:
                            json_response = response.json()
                            self.logger.debug(f"JSON response keys: {list(json_response.keys()) if isinstance(json_response, dict) else 'not dict'}")
                            # Handle different JSON response formats
                            if isinstance(json_response, dict):
                                if 'audio' in json_response:
                                    # Base64 encoded audio
                                    return base64.b64decode(json_response['audio'])
                                elif 'url' in json_response:
                                    # URL to audio file
                                    audio_response = requests.get(json_response['url'])
                                    return audio_response.content
                                elif 'data' in json_response:
                                    return json_response['data']
                        except Exception as e:
                            self.logger.warning(f"Failed to parse JSON response: {e}")
                    
                    self.logger.debug(f"First 16 bytes (hex): {response.content[:16].hex()}")
                    return response.content
                elif response.status_code == 429:
                    # Rate limit hit
                    wait_time = (2 ** attempt) * 5  # Exponential backoff
                    self.logger.warning(f"Rate limit hit. Waiting {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    self.logger.error(f"API error {response.status_code}: {response.text}")
                    if attempt == self.retry_attempts - 1:
                        response.raise_for_status()
                        
            except requests.exceptions.Timeout as e:
                timeout_msg = f"Request timeout after {dynamic_timeout if 'dynamic_timeout' in locals() else self.timeout}s (attempt {attempt + 1}/{self.retry_attempts})"
                self.logger.warning(timeout_msg)
                
                # Exponential backoff with jitter
                if attempt < self.retry_attempts - 1:
                    backoff_time = (2 ** attempt) + (attempt * 2)  # More aggressive backoff
                    self.logger.info(f"Retrying in {backoff_time} seconds...")
                    time.sleep(backoff_time)
                else:
                    self.logger.error(f"All retry attempts failed due to timeout. Text length: {len(text)} chars")
                    raise TimeoutError(f"TTS generation failed after {self.retry_attempts} attempts: {str(e)}")
                
            except requests.exceptions.RequestException as e:
                self.logger.error(f"Request failed: {e}")
                
                # Different handling for different error types
                if "connection" in str(e).lower():
                    self.logger.warning("Connection error detected - using longer backoff")
                    backoff_time = (2 ** attempt) * 3
                else:
                    backoff_time = 2 ** attempt
                
                if attempt < self.retry_attempts - 1:
                    self.logger.info(f"Retrying in {backoff_time} seconds...")
                    time.sleep(backoff_time)
                else:
                    self.logger.error(f"All retry attempts exhausted. Final error: {str(e)}")
                    raise
        
        raise Exception("All retry attempts failed")
    
    def batch_generate(self, text_chunks: List[str], voice: str = None) -> List[bytes]:
        """Generate audio for multiple text chunks"""
        self.logger.info(f"Starting batch generation for {len(text_chunks)} chunks")
        audio_chunks = []
        
        for i, text_chunk in enumerate(text_chunks):
            self.logger.info(f"Processing chunk {i + 1}/{len(text_chunks)}")
            audio_data = self.generate_audio(text_chunk, voice)
            audio_chunks.append(audio_data)
            
            # Rate limiting
            if i < len(text_chunks) - 1:  # Don't sleep after last chunk
                sleep_time = 60 / self.rate_limit  # Respect rate limit
                time.sleep(sleep_time)
        
        self.logger.info("Batch generation completed")
        return audio_chunks
    
    def test_connection(self) -> bool:
        """Test API connection with a simple request"""
        try:
            test_audio = self.generate_audio("Test connection.", "tara")
            return len(test_audio) > 0
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False
