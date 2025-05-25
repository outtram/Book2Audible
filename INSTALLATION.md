# Installation Guide

## What's NOT in GitHub (and needs to be installed/configured separately)

### 1. Python Environment
```bash
# Create virtual environment
python -m venv book2audible-env
source book2audible-env/bin/activate  # On Windows: book2audible-env\Scripts\activate
```

### 2. Dependencies
```bash
# Install Python packages
pip install -r requirements.txt

# Or install in development mode
pip install -e .[dev]
```

### 3. Environment Configuration
```bash
# Copy the example environment file
cp .env.example .env

# Edit .env with your actual values:
# - Add your Baseten API key
# - Adjust paths and settings as needed
```

### 4. Required External Services
- **Baseten Account**: Sign up at https://baseten.co for Orpheus TTS access
- **API Key**: Get your Baseten API key and add to `.env`

### 5. Directory Structure Setup
The following directories are created automatically but are empty in git:
- `data/input/` - Place your book files here
- `data/output/` - Generated audio files will be saved here  
- `data/logs/` - Application logs will be written here

### 6. System Dependencies
Depending on your OS, you may need:
- **ffmpeg** (for audio processing with pydub)
- **Python 3.9+**

### Quick Setup
```bash
git clone <your-repo-url>
cd Book2Audible
python -m venv book2audible-env
source book2audible-env/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env with your Baseten API key
```

## What IS in GitHub
- All source code (`src/`)
- Configuration templates (`config/`)
- Documentation
- Requirements and setup files
- Build scripts
- Example environment file (`.env.example`)