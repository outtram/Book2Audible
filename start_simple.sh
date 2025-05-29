#!/bin/bash

echo "🚀 Book2Audible Web Interface"
echo "=============================="

# Install Python dependencies quietly
echo "📦 Installing Python dependencies..."
pip install -q fastapi uvicorn python-multipart websockets pydantic

# Check Node.js
if ! command -v node &> /dev/null; then
    echo "❌ Node.js not found. Install from: https://nodejs.org/"
    echo "🔧 Starting backend only..."
    python3 start_backend_only.py
    exit 0
fi

echo "✅ Node.js found: $(node --version)"

# Install frontend dependencies if needed
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend && npm install && cd ..
fi

echo ""
echo "🌐 To start the full web interface:"
echo "📱 Backend: python3 start_backend_only.py (in one terminal)"
echo "⚛️  Frontend: cd frontend && npm run dev (in another terminal)"
echo ""
echo "🔧 Starting backend now..."
python3 start_backend_only.py