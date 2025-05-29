# Book2Audible Web Interface

A complete web interface for converting books to audiobooks using Orpheus TTS.

## 🚀 Quick Start

1. **Start the web interface:**
   ```bash
   ./start_web.sh
   ```

2. **Open your browser:**
   - Frontend: http://localhost:3000
   - API Documentation: http://localhost:8000/docs

## 🌟 Features

### ✅ Complete User Interface
- **Landing Page**: Hero section with call-to-action
- **File Upload**: Drag & drop for TXT/DOCX files
- **Configuration**: Provider and voice selection
- **Real-time Progress**: Live updates during conversion
- **Results & Download**: Individual and bulk chapter downloads

### ✅ Backend API
- **FastAPI**: Modern Python web framework
- **WebSocket Support**: Real-time progress updates
- **File Handling**: Secure upload and processing
- **Provider Integration**: Fal.ai and Baseten support

### ✅ Advanced Features
- **Resume Processing**: Continue interrupted conversions
- **Audio Preview**: Play chapters before download
- **Verification Reports**: Detailed quality analysis
- **Connection Testing**: Provider status monitoring

## 🎯 User Flow

1. **Upload** → Drag & drop your book file
2. **Configure** → Select TTS provider and voice
3. **Process** → Watch real-time conversion progress
4. **Download** → Get individual chapters or ZIP bundle

## 🛠️ Technical Stack

### Frontend
- **React 18** with TypeScript
- **Tailwind CSS** for styling
- **Vite** for development
- **React Router** for navigation
- **Axios** for API calls
- **React Dropzone** for file uploads

### Backend
- **FastAPI** for API endpoints
- **WebSockets** for real-time updates
- **Uvicorn** ASGI server
- **Your existing Book2AudioProcessor**

## 📁 Project Structure

```
Book2Audible/
├── web_api.py              # FastAPI backend
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/     # Reusable components
│   │   ├── pages/          # Main application pages
│   │   ├── hooks/          # Custom React hooks
│   │   ├── types/          # TypeScript definitions
│   │   └── utils/          # API and helper functions
│   └── package.json        # Frontend dependencies
├── start_web.sh           # Startup script
└── requirements.txt       # Updated with web dependencies
```

## 🔧 API Endpoints

### Core Operations
- `POST /api/upload` - Upload book file
- `POST /api/convert/{job_id}` - Start conversion
- `GET /api/status/{job_id}` - Get job status
- `WS /ws/{job_id}` - Real-time progress updates

### Configuration
- `GET /api/providers` - Available TTS providers
- `GET /api/voices` - Available voices
- `GET /api/test-connection` - Test provider connections

### Downloads
- `GET /api/download/{job_id}` - Download all chapters (ZIP)
- `GET /static/{file_path}` - Individual audio files

## 🚦 Running Individually

### Backend Only
```bash
python web_api.py
# Access at http://localhost:8000
```

### Frontend Only
```bash
cd frontend
npm install
npm run dev
# Access at http://localhost:3000
```

## 🎨 Customization

The interface uses your original designs with:
- **Color Scheme**: Green theme (`#019863`, `#46a080`, `#f8fcfa`)
- **Typography**: Inter and Noto Sans fonts
- **Components**: Matching your HTML mockups exactly

## 🔍 Monitoring

- **Logs**: Check console for detailed processing logs
- **WebSocket**: Real-time connection status
- **API Docs**: Interactive documentation at `/docs`

## 🛡️ Security

- **File Validation**: Type and size limits
- **CORS**: Configured for local development
- **Error Handling**: Comprehensive error messages
- **Timeout Protection**: Prevents hanging requests

---

**Perfect integration** with your existing CLI tool and robust backend! 🎉