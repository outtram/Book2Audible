#!/bin/bash

echo "🚀 Starting Book2Audible Web Interface"
echo "======================================"

# Check if Python dependencies are installed
echo "📦 Installing Python dependencies..."
pip install -r requirements.txt

# Check if Node.js is available
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js to run the frontend."
    echo "   Visit: https://nodejs.org/"
    exit 1
fi

# Install frontend dependencies if needed
if [ ! -d "frontend/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd frontend
    npm install
    cd ..
fi

echo "🌐 Starting services..."

# Start FastAPI backend in background
echo "🔧 Starting FastAPI backend on http://localhost:8000"
python web_api.py &
BACKEND_PID=$!

# Wait a moment for backend to start
sleep 3

# Start React frontend in background
echo "⚛️  Starting React frontend on http://localhost:3000"
cd frontend
npm run dev &
FRONTEND_PID=$!

echo ""
echo "✅ Web interface is starting!"
echo "📱 Frontend: http://localhost:3000"
echo "🔧 Backend API: http://localhost:8000"
echo "📚 API Docs: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop both services"

# Function to cleanup background processes
cleanup() {
    echo ""
    echo "🛑 Stopping services..."
    kill $BACKEND_PID 2>/dev/null
    kill $FRONTEND_PID 2>/dev/null
    exit 0
}

# Set trap to cleanup on script exit
trap cleanup SIGINT SIGTERM

# Wait for user to stop
wait