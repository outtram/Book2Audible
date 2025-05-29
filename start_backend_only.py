#!/usr/bin/env python3
"""
Start just the FastAPI backend for testing
"""
import subprocess
import sys
import os
from pathlib import Path

def check_dependencies():
    """Check if required Python packages are installed"""
    required_packages = ['fastapi', 'uvicorn', 'websockets', 'pydantic']
    missing = []
    
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"❌ Missing packages: {', '.join(missing)}")
        print("📦 Installing missing dependencies...")
        subprocess.check_call([sys.executable, '-m', 'pip', 'install'] + missing)
        print("✅ Dependencies installed!")

def main():
    print("🚀 Starting Book2Audible Backend")
    print("=" * 40)
    
    # Check dependencies
    check_dependencies()
    
    # Ensure output directory exists
    Path("data/output").mkdir(parents=True, exist_ok=True)
    
    print("🔧 Starting FastAPI backend...")
    print("📱 API will be available at: http://localhost:8000")
    print("📚 API Documentation: http://localhost:8000/docs")
    print("🧪 Test endpoint: http://localhost:8000/api/test-connection")
    print()
    print("Press Ctrl+C to stop")
    print()
    
    # Start the server
    try:
        import uvicorn
        uvicorn.run(
            "web_api:app",
            host="0.0.0.0",
            port=8000,
            reload=True,
            log_level="info"
        )
    except KeyboardInterrupt:
        print("\n🛑 Backend stopped")
    except Exception as e:
        print(f"❌ Error starting backend: {e}")

if __name__ == "__main__":
    main()