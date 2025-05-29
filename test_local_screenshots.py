#!/usr/bin/env python3
"""Test local development servers with screenshots."""

import asyncio
from screenshot_tester import ScreenshotTester


async def main():
    """Test local servers."""
    tester = ScreenshotTester()
    
    print("Testing local development servers...")
    
    try:
        # Test backend API
        print("Taking screenshot of backend at http://localhost:8000...")
        await tester.take_screenshot("http://localhost:8000", "backend_test")
        
        # Test frontend
        print("Taking screenshot of frontend at http://localhost:3001...")
        await tester.take_screenshot("http://localhost:3001", "frontend_test")
        
        print("Local server screenshots completed!")
        
    except Exception as e:
        print(f"Error testing local servers: {e}")


if __name__ == "__main__":
    asyncio.run(main())