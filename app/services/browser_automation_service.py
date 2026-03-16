"""
Browser Automation Service using Playwright
Allows AI to control browser for web interactions
"""
import asyncio
import json
from typing import Optional, Dict, Any, List
from pathlib import Path

class BrowserAutomationService:
    def __init__(self):
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.is_initialized = False
    
    async def init(self, headless: bool = False):
        """Initialize Playwright and launch browser"""
        try:
            from playwright.async_api import async_playwright
            self.playwright = await async_playwright().start()
            self.browser = await self.playwright.chromium.launch(
                headless=headless,
                args=['--start-maximized']
            )
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080}
            )
            self.page = await self.context.new_page()
            self.is_initialized = True
            return {"success": True, "message": "Browser initialized"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def open_url(self, url: str) -> Dict[str, Any]:
        """Open a URL in the browser"""
        if not self.is_initialized:
            await self.init()
        try:
            await self.page.goto(url, wait_until="domcontentloaded")
            title = await self.page.title()
            return {"success": True, "url": url, "title": title}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def search_github(self, query: str) -> Dict[str, Any]:
        """Search GitHub and return results"""
        if not self.is_initialized:
            await self.init()
        try:
            await self.page.goto("https://github.com", wait_until="domcontentloaded")
            await self.page.fill('input[name="q"]', query)
            await self.page.press('input[name="q"]', 'Enter')
            await self.page.wait_for_load_state("networkidle")
            
            results = []
            items = await self.page.query_selector_all('div[data-testid="results-list"] div')
            for item in items[:10]:
                try:
                    title_elem = await item.query_selector('a')
                    title = await title_elem.inner_text() if title_elem else ""
                    href = await title_elem.get_attribute('href') if title_elem else ""
                    if title and href:
                        results.append({"title": title.strip(), "url": href})
                except:
                    continue
            
            return {"success": True, "results": results, "query": query}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def click(self, selector: str) -> Dict[str, Any]:
        """Click an element by CSS selector"""
        try:
            await self.page.click(selector)
            return {"success": True, "selector": selector}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def fill(self, selector: str, text: str) -> Dict[str, Any]:
        """Fill input field"""
        try:
            await self.page.fill(selector, text)
            return {"success": True, "selector": selector, "text": text}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def type_text(self, selector: str, text: str, delay: int = 50) -> Dict[str, Any]:
        """Type text with delay"""
        try:
            await self.page.type(selector, text, delay=delay)
            return {"success": True, "selector": selector, "text": text}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def press_key(self, key: str) -> Dict[str, Any]:
        """Press a keyboard key"""
        try:
            await self.page.keyboard.press(key)
            return {"success": True, "key": key}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def get_text(self, selector: str) -> Dict[str, Any]:
        """Get text content of element"""
        try:
            element = await self.page.query_selector(selector)
            if element:
                text = await element.inner_text()
                return {"success": True, "text": text, "selector": selector}
            return {"success": False, "message": "Element not found"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def get_html(self, selector: str = None) -> Dict[str, Any]:
        """Get HTML content of page or element"""
        try:
            if selector:
                element = await self.page.query_selector(selector)
                html = await element.inner_html() if element else ""
            else:
                html = await self.page.content()
            return {"success": True, "html": html}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def screenshot(self, path: str = None) -> Dict[str, Any]:
        """Take a screenshot"""
        try:
            if not path:
                path = "screenshot.png"
            await self.page.screenshot(path=path, full_page=True)
            return {"success": True, "path": path}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def scroll(self, x: int = 0, y: int = 500) -> Dict[str, Any]:
        """Scroll the page"""
        try:
            await self.page.evaluate(f"window.scrollBy({x}, {y})")
            return {"success": True, "x": x, "y": y}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def wait_for_selector(self, selector: str, timeout: int = 30000) -> Dict[str, Any]:
        """Wait for element to appear"""
        try:
            await self.page.wait_for_selector(selector, timeout=timeout)
            return {"success": True, "selector": selector}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def get_element_attributes(self, selector: str) -> Dict[str, Any]:
        """Get all attributes of an element"""
        try:
            element = await self.page.query_selector(selector)
            if element:
                attrs = await self.page.evaluate("""(el) => {
                    let attrs = {};
                    for (let i = 0; i < el.attributes.length; i++) {
                        attrs[el.attributes[i].name] = el.attributes[i].value;
                    }
                    return attrs;
                }""", element)
                return {"success": True, "attributes": attrs}
            return {"success": False, "message": "Element not found"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def new_tab(self, url: str = "about:blank") -> Dict[str, Any]:
        """Open a new tab"""
        try:
            new_page = await self.context.new_page()
            await new_page.goto(url, wait_until="domcontentloaded")
            return {"success": True, "url": url}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def close_tab(self, page_index: int = 1) -> Dict[str, Any]:
        """Close a tab by index"""
        try:
            pages = self.context.pages
            if page_index < len(pages):
                await pages[page_index].close()
                return {"success": True}
            return {"success": False, "message": "Tab not found"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def switch_tab(self, page_index: int) -> Dict[str, Any]:
        """Switch to a tab by index"""
        try:
            pages = self.context.pages
            if page_index < len(pages):
                self.page = pages[page_index]
                return {"success": True, "index": page_index}
            return {"success": False, "message": "Tab not found"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def execute_script(self, script: str) -> Dict[str, Any]:
        """Execute JavaScript in the page"""
        try:
            result = await self.page.evaluate(script)
            return {"success": True, "result": result}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    async def close(self) -> Dict[str, Any]:
        """Close the browser"""
        try:
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
            self.is_initialized = False
            return {"success": True, "message": "Browser closed"}
        except Exception as e:
            return {"success": False, "message": str(e)}
    
    def is_available(self) -> bool:
        """Check if Playwright is installed"""
        try:
            import playwright
            return True
        except ImportError:
            return False

browser_service = BrowserAutomationService()
