# CLAUDE.md - Book2Audible Development Guide

## Project Overview

**Book2Audible** converts a 200,000-character ADHD book into high-quality audiobook using Orpheus TTS (Tara voice) on Baseten platform. Output: individual WAV files per chapter with seamless Australian English pronunciation.

## Tech Stack

- **Python 3.9+** - Core application
- **Baseten API** - Orpheus TTS hosting
- **Orpheus TTS Model** - Text-to-speech conversion
- **WAV Processing** - Audio manipulation and stitching
- **Optional**: React/NextJS frontend for user interface

## Architecture

```
├── src/
│   ├── core/
│   │   ├── text_processor.py      # Chapter detection & text cleaning
│   │   ├── tts_client.py          # Baseten API integration
│   │   ├── audio_processor.py     # WAV stitching & quality control
│   │   └── config.py              # Settings & constants
│   ├── utils/
│   │   ├── file_handler.py        # File I/O operations
│   │   ├── logger.py              # Detailed logging system
│   │   └── validators.py          # Input validation
│   └── tests/
│       ├── unit/                  # Component tests
│       ├── integration/           # End-to-end tests
│       └── quality/               # Audio quality validation
├── data/
│   ├── input/                     # Source book files
│   ├── output/                    # Generated WAV files
│   └── logs/                      # Processing logs
└── config/
    ├── baseten_config.json        # API settings
    └── tts_settings.json          # Voice & audio parameters
```

## Development Phases

### Phase 1: Environment & Research (Week 1)
**Goals**: Setup foundation and understand Baseten limitations

#### Tasks:
1. **Baseten API Research**
   - Sign up for Baseten account
   - Test Orpheus TTS model access
   - Document API limits (max text length, rate limits, costs)
   - Verify Tara voice availability for Australian English

2. **Development Environment**
   ```bash
   # Setup virtual environment
   python -m venv book2audible-env
   source book2audible-env/bin/activate
   pip install requests python-docx pydub wave
   ```

3. **Initial Code Structure**
   - Create project directories
   - Setup basic configuration files
   - Implement logging framework
   - Create placeholder modules

#### Deliverables:
- Working Baseten API connection
- Project structure established
- API limitations documented
- Basic configuration system

### Phase 2: Text Processing Engine (Weeks 2-3)
**Goals**: Handle book text parsing and chapter detection

#### Core Components:

1. **Text Processor (`text_processor.py`)**
   ```python
   class TextProcessor:
       def detect_chapters(self, text: str) -> List[Chapter]
       def clean_text(self, text: str) -> str
       def chunk_long_text(self, text: str, max_length: int) -> List[str]
       def preprocess_australian_english(self, text: str) -> str
   ```

2. **File Handler (`file_handler.py`)**
   - Support .txt and .docx formats
   - Automatic encoding detection
   - Chapter boundary detection
   - Manual chapter override capability

#### Key Features:
- **Smart Chapter Detection**: Regex patterns for headings
- **Text Cleaning**: Remove formatting artifacts
- **Australian English**: Preserve regional spelling (prioritisation, colour, etc.)
- **Chunking Strategy**: Split at sentence boundaries if API limits exceeded

#### Deliverables:
- Chapter detection working on test files
- Text cleaning and preprocessing complete
- Chunking algorithm for long chapters
- Unit tests for all text processing functions

### Phase 3: TTS Integration & Audio Generation (Weeks 3-4)
**Goals**: Baseten API integration and audio file generation

#### Core Components:

1. **TTS Client (`tts_client.py`)**
   ```python
   class BaseTenTTSClient:
       def __init__(self, api_key: str, model_id: str)
       def generate_audio(self, text: str, voice: str = "tara") -> bytes
       def batch_generate(self, text_chunks: List[str]) -> List[bytes]
       def handle_rate_limits(self, retry_count: int = 3)
   ```

2. **Audio Processor (`audio_processor.py`)**
   ```python
   class AudioProcessor:
       def stitch_audio_chunks(self, audio_files: List[bytes]) -> bytes
       def normalize_audio(self, audio: bytes) -> bytes
       def export_wav(self, audio: bytes, filename: str, quality: str = "high")
       def validate_audio_quality(self, audio_file: str) -> bool
   ```

#### Technical Requirements:
- **Audio Format**: WAV, 44.1 kHz, 16-bit stereo
- **Voice Configuration**: Tara voice, Australian English settings
- **Seamless Stitching**: No cuts or overlaps between chunks
- **Error Handling**: API timeouts, rate limits, failed requests

#### Deliverables:
- Working Baseten API integration
- Audio generation for single chapters
- Seamless multi-chunk stitching
- High-quality WAV output
- Robust error handling and retries

### Phase 4: Quality Assurance & Testing (Week 5)
**Goals**: Comprehensive testing and quality validation

#### Testing Strategy:

1. **Unit Tests**
   - Text processing functions
   - API integration methods
   - Audio processing utilities
   - File handling operations

2. **Integration Tests**
   - End-to-end pipeline (text → audio)
   - Multiple chapter processing
   - Large file handling
   - Error recovery scenarios

3. **Quality Tests**
   ```python
   # Audio Quality Validation
   def test_audio_transcription():
       # Use Whisper to transcribe generated audio
       # Compare with original text for accuracy
       
   def test_australian_pronunciation():
       # Verify regional spelling preserved
       # Check pronunciation of AU-specific terms
       
   def test_seamless_stitching():
       # Analyze audio for cuts/overlaps
       # Verify consistent pacing
   ```

4. **Performance Tests**
   - 200,000 character processing time
   - Memory usage optimization
   - Concurrent API request handling
   - Cost per character analysis

#### Quality Metrics:
- **Accuracy**: >98% text-to-audio match
- **Audio Quality**: No detectable stitching artifacts
- **Performance**: <2 hours for full book processing
- **Cost Efficiency**: Track and optimize API usage

### Phase 5: CLI & Optional Web Interface (Week 6)
**Goals**: User-friendly interface and final optimization

#### Command Line Interface:
```bash
# Basic usage
python book2audible.py --input book.txt --output ./audio/

# Advanced options
python book2audible.py \
  --input book.docx \
  --output ./output/ \
  --voice tara \
  --quality high \
  --manual-chapters \
  --log-level debug
```

#### Optional Web Interface (React/NextJS):
- File upload component
- Progress tracking
- Chapter preview/editing
- Audio player for preview
- Download management

## Key Implementation Details

### Baseten API Integration
```python
# Example API call structure
import requests

class BaseTenClient:
    def __init__(self):
        self.api_key = os.getenv('BASETEN_API_KEY')
        self.model_id = "orpheus-tts-model-id"
        
    def generate_speech(self, text, voice="tara"):
        headers = {"Authorization": f"Api-Key {self.api_key}"}
        payload = {
            "text": text,
            "voice": voice,
            "language": "en-AU",  # Australian English
            "format": "wav",
            "sample_rate": 44100
        }
        response = requests.post(f"{self.base_url}/predict", 
                               json=payload, headers=headers)
        return response.content
```

### Audio Stitching Strategy
```python
from pydub import AudioSegment

def stitch_audio_seamlessly(audio_chunks):
    combined = AudioSegment.empty()
    
    for chunk in audio_chunks:
        # Add small fade in/out to prevent clicks
        chunk_audio = AudioSegment.from_wav(chunk)
        chunk_audio = chunk_audio.fade_in(50).fade_out(50)
        combined += chunk_audio
    
    # Normalize volume
    combined = combined.normalize()
    return combined
```

### Configuration Management
```json
// baseten_config.json
{
  "api_key": "${BASETEN_API_KEY}",
  "model_id": "orpheus-tts-3b",
  "max_text_length": 5000,
  "rate_limit_per_minute": 60,
  "retry_attempts": 3,
  "timeout": 30
}

// tts_settings.json
{
  "voice": "tara",
  "language": "en-AU",
  "sample_rate": 44100,
  "bit_depth": 16,
  "channels": 2,
  "format": "wav"
}
```

## Testing & Quality Assurance

### Critical Test Cases:
1. **Australian English Verification**
   - Test words: "prioritisation", "colour", "centre", "analyse"
   - Verify pronunciation matches AU standards
   
2. **Chapter Boundary Detection**
   - Test various heading formats
   - Handle edge cases (numbered chapters, Part I/II, etc.)
   
3. **Long Text Processing**
   - Test chunking at sentence boundaries
   - Verify no word cuts in audio
   - Check stitching quality
   
4. **Error Recovery**
   - API timeout handling
   - Rate limit management
   - Partial processing recovery

### Performance Benchmarks:
- **Target**: Process 200K characters in <2 hours
- **Memory**: <1GB peak usage
- **Cost**: <$50 for full book conversion
- **Quality**: Indistinguishable from professional audiobook

## Deployment & Production

### Environment Variables:
```bash
export BASETEN_API_KEY="your-api-key"
export LOG_LEVEL="INFO"
export OUTPUT_DIR="/path/to/audio/output"
export MAX_CONCURRENT_REQUESTS=3
```

### Production Considerations:
- **Cost Monitoring**: Track API usage and costs
- **Error Logging**: Comprehensive logging for debugging
- **Backup Strategy**: Save intermediate processing states
- **Scalability**: Design for multiple book processing

## Future Enhancements

### Phase 2 Features:
- Multiple voice options
- MP3 output format
- Batch book processing
- Web dashboard
- Integration with audiobook platforms

### Advanced Features:
- Chapter-specific voice settings
- Background music integration
- Automated QA with speech recognition
- Custom pronunciation dictionary
- Real-time processing preview

## Troubleshooting Guide

### Common Issues:
1. **API Rate Limits**: Implement exponential backoff
2. **Audio Quality**: Check sample rates and bit depths
3. **Memory Issues**: Process in smaller chunks
4. **Australian Pronunciation**: Verify language settings

### Debug Commands:
```bash
# Test API connection
python -c "from src.core.tts_client import BaseTenTTSClient; client = BaseTenTTSClient(); print(client.test_connection())"

# Validate audio output
python -c "from src.utils.validators import AudioValidator; AudioValidator.check_quality('output.wav')"

# Check text processing
python -c "from src.core.text_processor import TextProcessor; tp = TextProcessor(); print(tp.detect_chapters('sample.txt'))"
```

## Success Metrics

### MVP Success Criteria:
- ✅ Process 200K character book successfully
- ✅ Generate individual WAV files per chapter
- ✅ Maintain Australian English pronunciation
- ✅ Seamless audio with no artifacts
- ✅ Complete processing in <2 hours
- ✅ Comprehensive logging and error handling

**Ready to start Phase 1!** 🚀