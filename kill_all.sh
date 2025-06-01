#!/bin/bash

echo "🛑 Stopping Book2Audible services..."

# Kill processes on ports 8000 and 8001 (backend)
echo "Stopping backend services (ports 8000, 8001)..."
lsof -ti :8000 | xargs kill -9 2>/dev/null
lsof -ti :8001 | xargs kill -9 2>/dev/null

# Kill processes on port 3000 (frontend)
echo "Stopping frontend service (port 3000)..."
lsof -ti :3000 | xargs kill -9 2>/dev/null

# Kill any remaining Python processes related to Book2Audible
echo "Stopping remaining Book2Audible processes..."
pkill -f "web_api.py" 2>/dev/null
pkill -f "book2audible" 2>/dev/null

# Kill any Node.js processes running Vite
echo "Stopping Vite development server..."
pkill -f "vite" 2>/dev/null

echo "✅ All Book2Audible services stopped"
echo ""
echo "Checking remaining processes..."
echo "Port 8000:" 
lsof -i :8000 2>/dev/null || echo "  ✅ Port 8000 is free"
echo "Port 3000:"
lsof -i :3000 2>/dev/null || echo "  ✅ Port 3000 is free"
echo ""
echo "🎯 Ready to restart services with ./start_all.sh"