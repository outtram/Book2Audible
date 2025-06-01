# CLAUDE.md - Book2Audible Production System

## Project Overview

**Book2Audible** is a complete text-to-audiobook conversion system using Orpheus TTS on fal.ai platform. It features a full web interface, CLI tools, PDF extraction, and advanced audio verification. Successfully converts books into high-quality WAV files with Australian English pronunciation.

## Current Status: ✅ PRODUCTION READY

The system has evolved well beyond the original MVP into a full-featured production application with web interface, advanced verification, and comprehensive error handling.

## Tech Stack

- **Python 3.9+ Backend** - FastAPI web server + CLI tools
- **fal.ai API** - Primary TTS provider (Orpheus model)
- **Baseten API** - Fallback TTS provider
- **React + TypeScript Frontend** - Complete web interface
- **Tailwind CSS** - Styling and responsive design
- **WebSocket** - Real-time progress updates
- **Whisper STT** - Audio verification and quality assurance
- **PDF Extraction** - PyMuPDF for PDF text extraction

## Architecture (Current Implementation)

```
├── src/core/                     # ✅ Core processing engine
│   ├── text_processor.py         # Chapter detection & text cleaning
│   ├── fal_tts_client.py         # Fal.ai TTS integration (primary)
│   ├── tts_client.py             # Baseten TTS client (fallback)
│   ├── audio_processor.py        # Audio stitching & processing
│   ├── audio_verifier.py         # Whisper-based verification
│   ├── audio_file_verifier.py    # File validation
│   ├── pdf_extractor.py          # PDF text extraction
│   ├── processor.py              # Main processing pipeline
│   ├── buffer_manager.py         # Memory management
│   ├── helpers.py                # Utility functions
│   └── config.py                 # Configuration management
├── frontend/                     # ✅ Complete React web app
│   ├── src/
│   │   ├── App.tsx               # Main application
│   │   ├── components/Header.tsx # Navigation
│   │   ├── pages/                # All page components
│   │   │   ├── HomePage.tsx      # Landing page
│   │   │   ├── UploadPage.tsx    # File upload interface
│   │   │   ├── ConfigurePage.tsx # TTS settings
│   │   │   ├── ProcessingPage.tsx# Real-time progress
│   │   │   ├── ChaptersPage.tsx  # Chapter management
│   │   │   ├── ResultsPage.tsx   # Download & playback
│   │   │   └── HelpPage.tsx      # Documentation
│   │   ├── hooks/useWebSocket.ts # Real-time updates
│   │   ├── utils/api.ts          # Backend communication
│   │   └── types/index.ts        # TypeScript definitions
│   └── package.json              # Frontend dependencies
├── web_api.py                    # ✅ FastAPI backend server
├── book2audible.py               # ✅ CLI interface
├── config/                       # ✅ Configuration files
│   ├── fal_config.json          # Fal.ai API settings
│   ├── baseten_config.json      # Baseten fallback settings
│   └── tts_settings.json        # Audio & processing settings
├── data/
│   ├── input/                   # Source files (PDF, TXT)
│   ├── output/                  # Generated audio files
│   └── logs/                    # Processing & verification logs
└── chapters/                    # Pre-extracted chapter files
```

## Current Features (All Working)

### ✅ Core Processing
- **Multi-format Input**: PDF, TXT file support with automatic encoding detection
- **Smart Chapter Detection**: Regex-based chapter boundary detection
- **Text Chunking**: Intelligent sentence-boundary chunking for API limits
- **Dual TTS Providers**: Fal.ai primary, Baseten fallback
- **Audio Quality**: 24kHz, 16-bit mono WAV optimized for speech

### ✅ Web Interface
- **Modern React UI**: TypeScript, Tailwind CSS, responsive design
- **File Upload**: Drag-and-drop interface for PDF/TXT files
- **Real-time Progress**: WebSocket updates during processing
- **Configuration**: Voice settings, provider selection, quality options
- **Results Management**: Audio playback, individual chapter downloads, ZIP exports
- **Job Resume**: Continue failed or interrupted processing jobs

### ✅ Advanced Verification
- **Whisper Integration**: Automatic transcription of generated audio
- **Accuracy Checking**: Compare original text vs transcribed audio
- **HTML Diff Reports**: Visual comparison with highlighted differences
- **Coverage Analysis**: Ensure all text chunks are processed
- **Quality Metrics**: Transcription accuracy and word coverage stats

### ✅ CLI Tools
- **Simple Processing**: `python book2audible.py -i book.pdf -p fal`
- **PDF Extraction**: `python book2audible.py --extract-pdf book.pdf`
- **Connection Testing**: `python book2audible.py --test-connection`
- **Provider Selection**: Support for both fal.ai and Baseten APIs
- **Resume Jobs**: Continue processing from interruption points

### ✅ Production Features
- **Comprehensive Logging**: Detailed processing and verification logs
- **Error Recovery**: Automatic retries with exponential backoff
- **Rate Limiting**: Intelligent delays to respect API limits
- **Memory Management**: Efficient chunk processing for large files
- **Timeout Handling**: Per-chunk timeouts with graceful recovery

## Configuration (Current)

### Fal.ai Configuration (`config/fal_config.json`)
```json
{
  "api_key": "your-fal-api-key",
  "model_id": "fal-ai/orpheus-tts"
}
```

### TTS Settings (`config/tts_settings.json`)
```json
{
  "voice": "tara",
  "sample_rate": 24000,
  "channels": 1,
  "verification_enabled": true,
  "chunk_size": 150,
  "chunk_delay": 2,
  "timeout": 60,
  "max_retries": 3
}
```

### Baseten Fallback (`config/baseten_config.json`)
```json
{
  "api_key": "your-baseten-api-key",
  "model_id": "orpheus-model-id",
  "endpoint": "your-endpoint-url"
}
```

## Usage

### Web Interface
```bash
# Start full application (backend + frontend)
./start_web.sh

# Access at http://localhost:3000
# Backend API at http://localhost:8000
```

### CLI Processing
```bash
# Basic usage
python book2audible.py -i book.pdf -p fal

# With verification
python book2audible.py -i book.txt -p fal --verify

# Extract PDF to chapters
python book2audible.py --extract-pdf book.pdf

# Test API connection
python book2audible.py --test-connection --provider fal
```

### Backend Only
```bash
# Start API server only
python web_api.py

# API available at http://localhost:8000
# Docs at http://localhost:8000/docs
```

## API Endpoints

The FastAPI backend provides comprehensive REST API:

- `POST /upload` - Upload and process files
- `GET /jobs/{job_id}` - Get job status and results
- `GET /jobs/{job_id}/chapters` - List generated chapters
- `GET /download/{job_id}/{chapter}` - Download individual chapters
- `GET /download/{job_id}/all` - Download all chapters as ZIP
- `WebSocket /ws/{job_id}` - Real-time progress updates

## Audio Verification System

The system includes comprehensive audio quality verification:

1. **Transcription**: Uses Whisper to convert audio back to text
2. **Comparison**: Compares original text with transcribed text
3. **Diff Reports**: Generates HTML reports highlighting differences
4. **Metrics**: Calculates word accuracy and coverage percentages
5. **Logging**: Detailed verification logs for quality assurance

## Testing & Quality Assurance

### Automated Testing
- Unit tests for core processing functions
- Integration tests for TTS providers
- Audio quality validation with Whisper
- End-to-end web interface testing

### Performance Metrics
- **Processing Speed**: ~5-10 minutes for 10,000 characters
- **Accuracy**: >95% transcription accuracy (measured via Whisper)
- **Quality**: 24kHz mono WAV files optimized for speech
- **Reliability**: Automatic retry and resume capabilities

## Deployment

### Environment Variables
```bash
export FAL_API_KEY="your-fal-api-key"
export BASETEN_API_KEY="your-baseten-api-key"  # Optional fallback
export LOG_LEVEL="INFO"
export VERIFICATION_ENABLED="true"
```

### Production Startup
```bash
# Install dependencies
pip install -r requirements.txt
cd frontend && npm install

# Start production services
./start_web.sh  # Full application
# or
./start_all.sh  # All services including monitoring
```

## Current Limitations & Known Issues

1. **Fal.ai Rate Limits**: 2-second delays between chunks
2. **Large Files**: Memory usage increases with file size
3. **PDF Extraction**: Complex layouts may need manual chapter marking
4. **Audio Format**: Currently mono output (stereo support planned)

## Recent Achievements

- ✅ Successfully converted 200,000+ character ADHD book
- ✅ Achieved >95% transcription accuracy
- ✅ Built complete web interface with real-time updates
- ✅ Implemented dual TTS provider failover
- ✅ Added comprehensive audio verification system
- ✅ Created production-ready deployment scripts

## Future Enhancements

### Short Term
- Stereo audio output option
- Multiple voice selection in web interface
- Batch processing for multiple books
- Enhanced PDF layout detection

### Long Term  
- Background music integration
- Custom pronunciation dictionary
- Mobile app development
- Cloud deployment options

## Troubleshooting

### Common Issues
1. **API Timeouts**: Check internet connection and API keys
2. **Memory Issues**: Process smaller chunks or increase system memory
3. **Audio Quality**: Verify TTS settings and API responses
4. **Web Interface**: Check both frontend and backend are running

### Debug Commands
```bash
# Test TTS connection
python book2audible.py --test-connection --provider fal

# Verify audio file
python -c "from src.core.audio_verifier import AudioVerifier; AudioVerifier().verify_audio('output.wav')"

# Check processing logs
tail -f data/logs/processing.log
```

## Success Metrics ✅

- ✅ Process 200K+ character books successfully
- ✅ Generate high-quality WAV files per chapter
- ✅ Maintain Australian English pronunciation (Tara voice)
- ✅ Seamless audio with no artifacts
- ✅ Complete web interface with real-time updates
- ✅ Comprehensive verification and quality assurance
- ✅ Production-ready with error handling and recovery

**Status: Production Ready & Actively Used** 🚀