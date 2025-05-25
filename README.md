# 🎧 Book2Audible

Convert text books to high-quality audiobooks using Orpheus TTS with Australian English pronunciation.

## 🚀 Quick Start

```bash
# Install
./install.sh

# Configure (add your Baseten API key)
cp .env.example .env
# Edit .env with BASETEN_API_KEY=your_key

# Test
python3 book2audible.py --test-connection

# Process book
python3 book2audible.py -i data/input/sample_adhd_book.txt
```

## ✨ Features

- **Orpheus TTS**: Baseten-hosted with Tara voice
- **Australian English**: Preserves colour, prioritise, analyse spellings
- **Auto Chapters**: Detects chapter breaks automatically
- **High Quality**: 44.1kHz 16-bit stereo WAV
- **Seamless Audio**: Perfect stitching, no cuts
- **CLI Interface**: Easy command-line usage

## 📖 Usage

```bash
# Basic usage
python3 book2audible.py -i book.txt

# Custom output
python3 book2audible.py -i book.txt -o ./audiobook/

# Manual chapters
python3 book2audible.py -i book.txt -m "Chapter 1" -m "Chapter 2"

# Debug mode
python3 book2audible.py -i book.txt -l DEBUG
```

## 🏗️ Architecture

```
src/core/          # Main processing
src/utils/         # Utilities  
config/           # Settings
data/            # Input/output
tests/           # Test suite
```

## 🧪 Testing

```bash
pytest                    # All tests
pytest src/tests/unit/    # Unit tests
pytest --cov=src         # With coverage
```

## 🔧 Development

```bash
pip install -e ".[dev]"   # Dev install
black src/               # Format code
flake8 src/              # Lint
mypy src/                # Type check
```

## 📋 Requirements

- Python 3.9+
- Baseten API key
- 4GB+ RAM

## ⚙️ Configuration

Edit `.env`:
```
BASETEN_API_KEY=your_key
LOG_LEVEL=INFO
CHUNK_SIZE=4000
```

## 🎯 Australian English

Automatically preserves:
- colour → colour ✅
- prioritise → prioritise ✅  
- analyse → analyse ✅
- centre → centre ✅

## 🤝 Contributing

1. Fork repo
2. Create feature branch  
3. Add tests
4. Submit PR

Made with ❤️ in Australia 🇦🇺
