I can definitely help you run your Book2Audible project! This is a sophisticated audiobook conversion system with both CLI and web interfaces.

## 🎧 Book2Audible - Complete Setup & Run Guide

Your project converts text books to high-quality audiobooks using Orpheus TTS with Australian English pronunciation.

### 🚀 **Quick Start (Recommended)**

1. **Install & Setup:**
```bash
./install.sh
```

2. **Configure API Key:**
```bash
cp .env.example .env
# Edit .env and add your Baseten API key
```

3. **Test Connection:**
```bash
python3 book2audible.py --test-connection
```

4. **Run Full Web Application:**
```bash
./start_all.sh
```
This starts both:
- Backend API server on `http://localhost:8000`
- Frontend web interface on `http://localhost:3000`

### 🎯 **Different Ways to Run**

#### **1. Web Interface (Full Stack)**
```bash
./start_all.sh
```
- Complete web UI for uploading, processing, and managing audiobooks
- Real-time progress tracking
- Audio player with synchronization

#### **2. Command Line Interface**
```bash
# Basic conversion
python3 book2audible.py -i book.txt

# Extract chapters from PDF first
python3 book2audible.py --extract-pdf book.pdf -o ./extracted_chapters/

# Process with custom output
python3 book2audible.py -i book.txt -o ./audiobook/
```

#### **3. Backend Only**
```bash
python3 start_backend_only.py
```

### 🔧 **Project Features**

- **🎤 Orpheus TTS**: High-quality Australian English voice (Tara)
- **📚 PDF Extraction**: Automatically extract chapters from PDF books
- **🔄 Auto Chapters**: Intelligent chapter detection
- **🎵 High Quality**: 44.1kHz 16-bit stereo WAV output
- **🌐 Web Interface**: Modern React/TypeScript frontend
- **📊 Progress Tracking**: Real-time processing updates

### 📁 **Your Current Setup**

You already have:
- ✅ Extracted chapters in `chapters/chapters/`
- ✅ Configuration files set up
- ✅ Frontend built with React/TypeScript
- ✅ Multiple startup scripts for different use cases
- ✅ Sample ADHD book PDF ready for processing

### 🛑 **To Stop Services**
```bash
./kill_all.sh
```

The project is well-structured and ready to run. Start with [`./install.sh`](install.sh:1), configure your API key in [`.env`](.env.example:2), then run [`./start_all.sh`](start_all.sh:1) for the complete web experience.