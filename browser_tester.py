#!/usr/bin/env python3
"""
Browser automation and testing script using Playwright
Can open URLs, interact with pages, take screenshots, and validate content
"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
import click
from datetime import datetime

class BrowserTester:
    def __init__(self, headless=True, browser_type="chromium"):
        """Initialize browser tester
        
        Args:
            headless: Run browser without GUI (False to see browser)
            browser_type: 'chromium', 'firefox', or 'webkit'
        """
        self.headless = headless
        self.browser_type = browser_type
        self.screenshots_dir = Path("screenshots")
        self.screenshots_dir.mkdir(exist_ok=True)
        
    def test_webpage(self, url, actions=None, screenshot_name=None):
        """Test a webpage with optional actions and screenshot
        
        Args:
            url: URL to visit
            actions: List of actions to perform
            screenshot_name: Name for screenshot file
        
        Returns:
            dict: Test results including screenshot path and page info
        """
        with sync_playwright() as p:
            # Launch browser
            if self.browser_type == "chromium":
                browser = p.chromium.launch(headless=self.headless)
            elif self.browser_type == "firefox":
                browser = p.firefox.launch(headless=self.headless)
            else:
                browser = p.webkit.launch(headless=self.headless)
            
            page = browser.new_page()
            
            try:
                # Navigate to URL
                print(f"📱 Opening: {url}")
                page.goto(url)
                
                # Wait for page to load
                page.wait_for_load_state("networkidle")
                
                # Get page info
                title = page.title()
                print(f"📄 Page title: {title}")
                
                # Perform actions if provided
                results = {"url": url, "title": title, "actions_performed": []}
                
                if actions:
                    for action in actions:
                        result = self._perform_action(page, action)
                        results["actions_performed"].append(result)
                
                # Take screenshot
                if screenshot_name:
                    screenshot_path = self.screenshots_dir / f"{screenshot_name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                else:
                    screenshot_path = self.screenshots_dir / f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                
                page.screenshot(path=str(screenshot_path), full_page=True)
                print(f"📸 Screenshot saved: {screenshot_path}")
                results["screenshot"] = str(screenshot_path)
                
                return results
                
            except Exception as e:
                print(f"❌ Error: {e}")
                return {"error": str(e)}
            finally:
                browser.close()
    
    def _perform_action(self, page, action):
        """Perform a single action on the page"""
        action_type = action.get("type")
        
        try:
            if action_type == "click":
                selector = action.get("selector")
                page.click(selector)
                return {"type": "click", "selector": selector, "status": "success"}
                
            elif action_type == "fill":
                selector = action.get("selector")
                text = action.get("text")
                page.fill(selector, text)
                return {"type": "fill", "selector": selector, "text": text, "status": "success"}
                
            elif action_type == "wait":
                seconds = action.get("seconds", 1)
                page.wait_for_timeout(seconds * 1000)
                return {"type": "wait", "seconds": seconds, "status": "success"}
                
            elif action_type == "scroll":
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                return {"type": "scroll", "status": "success"}
                
            elif action_type == "check_text":
                text = action.get("text")
                if page.get_by_text(text).count() > 0:
                    return {"type": "check_text", "text": text, "status": "found"}
                else:
                    return {"type": "check_text", "text": text, "status": "not_found"}
                    
            else:
                return {"type": action_type, "status": "unknown_action"}
                
        except Exception as e:
            return {"type": action_type, "status": "error", "error": str(e)}

    def capture_desktop_screenshot(self, filename=None):
        """Capture full desktop screenshot (macOS only)"""
        if filename is None:
            filename = f"desktop_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        screenshot_path = self.screenshots_dir / filename
        
        # Use macOS screencapture command
        import subprocess
        try:
            subprocess.run(["screencapture", "-x", str(screenshot_path)], check=True)
            print(f"🖥️ Desktop screenshot saved: {screenshot_path}")
            return str(screenshot_path)
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to capture desktop: {e}")
            return None


@click.command()
@click.option('--url', '-u', help='URL to test')
@click.option('--headless/--no-headless', default=True, help='Run browser in headless mode')
@click.option('--browser', '-b', default='chromium', 
              type=click.Choice(['chromium', 'firefox', 'webkit']),
              help='Browser to use')
@click.option('--screenshot', '-s', help='Screenshot filename (without extension)')
@click.option('--desktop', is_flag=True, help='Capture desktop screenshot instead')
@click.option('--actions', '-a', help='JSON file with actions to perform')
def main(url, headless, browser, screenshot, desktop, actions):
    """Browser testing and screenshot tool using Playwright
    
    Examples:
        # Simple screenshot
        python browser_tester.py -u https://google.com -s google_homepage
        
        # Visible browser (see what's happening)
        python browser_tester.py -u https://google.com --no-headless
        
        # Desktop screenshot
        python browser_tester.py --desktop
        
        # Test local file
        python browser_tester.py -u file:///path/to/index.html
    """
    
    tester = BrowserTester(headless=headless, browser_type=browser)
    
    if desktop:
        tester.capture_desktop_screenshot()
        return
    
    if not url:
        click.echo("❌ Error: URL required (use --url or -u)")
        return
    
    # Load actions if provided
    action_list = None
    if actions:
        import json
        with open(actions, 'r') as f:
            action_list = json.load(f)
    
    # Test the webpage
    results = tester.test_webpage(url, action_list, screenshot)
    
    # Display results
    if "error" in results:
        click.echo(f"❌ Test failed: {results['error']}")
    else:
        click.echo("✅ Test completed successfully!")
        click.echo(f"📄 Title: {results['title']}")
        if results.get("actions_performed"):
            click.echo("🎬 Actions performed:")
            for action in results["actions_performed"]:
                click.echo(f"  • {action['type']}: {action['status']}")


if __name__ == "__main__":
    main()