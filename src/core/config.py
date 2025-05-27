"""
Configuration management for Book2Audible
"""
import json
import os
from pathlib import Path
from typing import Dict, Any
from dotenv import load_dotenv

class Config:
    """Central configuration management"""
    
    def __init__(self):
        # Load environment variables
        load_dotenv()
        
        # Base paths
        self.project_root = Path(__file__).parent.parent.parent
        self.config_dir = self.project_root / "config"
        self.data_dir = self.project_root / "data"
        
        # Load configurations
        self.baseten_config = self._load_json_config("baseten_config.json")
        self.fal_config = self._load_json_config("fal_config.json")
        self.tts_settings = self._load_json_config("tts_settings.json")
        
        # Process environment variables
        self._process_env_vars()
        
    def _load_json_config(self, filename: str) -> Dict[str, Any]:
        """Load JSON configuration file"""
        config_path = self.config_dir / filename
        if not config_path.exists():
            raise FileNotFoundError(f"Configuration file not found: {config_path}")
            
        with open(config_path, 'r') as f:
            config = json.load(f)
            
        # Replace environment variables in strings
        return self._replace_env_vars(config)
    
    def _replace_env_vars(self, obj):
        """Recursively replace ${ENV_VAR} patterns with environment variables"""
        if isinstance(obj, dict):
            return {k: self._replace_env_vars(v) for k, v in obj.items()}
        elif isinstance(obj, list):
            return [self._replace_env_vars(item) for item in obj]
        elif isinstance(obj, str) and obj.startswith("${") and obj.endswith("}"):
            env_var = obj[2:-1]  # Remove ${ and }
            return os.getenv(env_var, obj)  # Return original if env var not found
        else:
            return obj
    
    def _process_env_vars(self):
        """Process additional environment variables"""
        self.log_level = os.getenv("LOG_LEVEL", "INFO")
        self.log_file = self.project_root / os.getenv("LOG_FILE", "data/logs/book2audible.log")
        self.max_concurrent_requests = int(os.getenv("MAX_CONCURRENT_REQUESTS", "3"))
        self.chunk_size = int(os.getenv("CHUNK_SIZE", "1000"))
        self.output_dir = self.project_root / os.getenv("OUTPUT_DIR", "data/output")
        self.input_dir = self.project_root / os.getenv("INPUT_DIR", "data/input")
        self.audio_quality = os.getenv("AUDIO_QUALITY", "high")
        self.enable_quality_check = os.getenv("ENABLE_QUALITY_CHECK", "true").lower() == "true"
        self.stt_model = os.getenv("STT_MODEL", "whisper")
        self.tts_provider = os.getenv("TTS_PROVIDER", "baseten")  # Default to baseten, can be "fal"
        
    @property
    def baseten_api_key(self) -> str:
        """Get Baseten API key"""
        return self.baseten_config.get("api_key", "")
        
    @property
    def model_id(self) -> str:
        """Get TTS model ID"""
        return self.baseten_config.get("model_id", "e3m0oe2q")
    
    @property
    def fal_api_key(self) -> str:
        """Get Fal.ai API key"""
        return self.fal_config.get("api_key", "")

# Global configuration instance
config = Config()
