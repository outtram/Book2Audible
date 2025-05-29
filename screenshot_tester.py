#!/usr/bin/env python3
"""
Website Screenshot Testing Tool using Playwright

This module provides functionality to take screenshots of websites for testing purposes.
Uses Playwright which is already installed in the project dependencies.
"""

import asyncio
import os
from datetime import datetime
from pathlib import Path
from playwright.async_api import async_playwright


class ScreenshotTester:
    """A class for taking screenshots of websites using Playwright."""
    
    def __init__(self, output_dir: str = "screenshots"):
        """
        Initialize the ScreenshotTester.
        
        Args:
            output_dir (str): Directory to save screenshots
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True)
    
    async def take_screenshot(self, url: str, name: str = None, wait_for_selector: str = None) -> str:
        """
        Take a screenshot of a website.
        
        Args:
            url (str): URL to take screenshot of
            name (str): Optional name for the screenshot file
            wait_for_selector (str): Optional CSS selector to wait for before taking screenshot
            
        Returns:
            str: Path to the saved screenshot file
        """
        if not name:
            # Generate name from URL and timestamp
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            clean_url = url.replace("://", "_").replace("/", "_").replace(".", "_")
            name = f"{clean_url}_{timestamp}"
        
        filename = f"{name}.png"
        filepath = self.output_dir / filename
        
        async with async_playwright() as p:
            # Launch browser
            browser = await p.chromium.launch()
            page = await browser.new_page()
            
            # Set viewport size
            await page.set_viewport_size({"width": 1920, "height": 1080})
            
            try:
                # Navigate to URL
                await page.goto(url, wait_until="networkidle")
                
                # Wait for specific selector if provided
                if wait_for_selector:
                    await page.wait_for_selector(wait_for_selector, timeout=10000)
                
                # Take screenshot
                await page.screenshot(path=str(filepath), full_page=True)
                
                print(f"Screenshot saved: {filepath}")
                return str(filepath)
                
            except Exception as e:
                print(f"Error taking screenshot: {e}")
                raise
            finally:
                await browser.close()
    
    async def take_multiple_screenshots(self, urls: list, wait_time: float = 2.0) -> list:
        """
        Take screenshots of multiple URLs.
        
        Args:
            urls (list): List of URLs to screenshot
            wait_time (float): Time to wait between screenshots
            
        Returns:
            list: List of screenshot file paths
        """
        screenshots = []
        
        for i, url in enumerate(urls):
            try:
                screenshot_path = await self.take_screenshot(url, f"site_{i+1}")
                screenshots.append(screenshot_path)
                
                if i < len(urls) - 1:  # Don't wait after the last screenshot
                    await asyncio.sleep(wait_time)
                    
            except Exception as e:
                print(f"Failed to screenshot {url}: {e}")
                continue
        
        return screenshots


async def main():
    """Example usage of the ScreenshotTester."""
    tester = ScreenshotTester()
    
    try:
        # Test external site first
        print("Taking screenshot of example.com...")
        await tester.take_screenshot("https://example.com", "example_test")
        
        # Test Google as another example
        print("Taking screenshot of google.com...")
        await tester.take_screenshot("https://google.com", "google_test")
        
        print("Screenshots completed successfully!")
        
    except Exception as e:
        print(f"Screenshot test failed: {e}")


if __name__ == "__main__":
    asyncio.run(main())