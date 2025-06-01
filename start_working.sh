#!/bin/bash

echo "🚀 Starting Book2Audible with your working commands..."

# Change to project directory
cd "$(dirname "$0")"

# Check if virtual environment exists and activate it
if [ -d "book2audible-env" ]; then
    echo "📦 Activating virtual environment..."
    source book2audible-env/bin/activate
fi

echo "🖥️  Starting backend API server..."
# Start backend in background (your exact working command)
python web_api.py &

echo "🌐 Starting frontend development server..."
# Start frontend (your exact working command)  
cd frontend && npm run dev

# This will keep the script running and show frontend output