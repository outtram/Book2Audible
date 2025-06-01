#!/bin/bash

echo "🚀 Starting Book2Audible services..."

# Change to project directory
cd "$(dirname "$0")"

# Check if we're in the right directory
if [ ! -f "web_api.py" ]; then
    echo "❌ Error: web_api.py not found. Make sure you're in the Book2Audible directory."
    exit 1
fi

if [ ! -d "frontend" ]; then
    echo "❌ Error: frontend directory not found. Make sure you're in the Book2Audible directory."
    exit 1
fi

# Check for virtual environment
if [ -d "book2audible-env" ]; then
    echo "📦 Activating virtual environment..."
    source book2audible-env/bin/activate
else
    echo "⚠️  Warning: book2audible-env virtual environment not found. Using system Python."
fi

# Start backend API server
echo "🖥️  Starting backend API server on port 8000..."
python web_api.py &
BACKEND_PID=$!

# Wait for backend to start (your working approach)
echo "⏳ Waiting for backend to start..."
sleep 5

# Simple check if backend is running
if curl -s http://localhost:8000/ > /dev/null; then
    echo "✅ Backend API started successfully (PID: $BACKEND_PID)"
else
    echo "⚠️  Backend may still be starting (PID: $BACKEND_PID)"
    echo "    This is normal - it will be available shortly"
fi

# Start frontend development server
echo "🌐 Starting frontend development server on port 3000..."
cd frontend

# Check if node_modules exists
if [ ! -d "node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    npm install
fi

npm run dev &
FRONTEND_PID=$!

# Wait a moment for frontend to start
sleep 5

# Check if frontend started successfully
if curl -s http://localhost:3000/ > /dev/null; then
    echo "✅ Frontend started successfully (PID: $FRONTEND_PID)"
else
    echo "❌ Frontend failed to start"
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit 1
fi

echo ""
echo "🎉 Book2Audible is now running!"
echo ""
echo "📍 Access URLs:"
echo "   Frontend: http://localhost:3000"
echo "   Backend API: http://localhost:8000"
echo ""
echo "📋 Process IDs:"
echo "   Backend PID: $BACKEND_PID"
echo "   Frontend PID: $FRONTEND_PID"
echo ""
echo "⏹️  To stop all services, run: ./kill_all.sh"
echo "📊 To check status, run: lsof -i :8000,3000"
echo ""
echo "✨ Happy audiobook creating!"