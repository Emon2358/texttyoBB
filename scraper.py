# scraper.py
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
import json
import logging
import sys
from datetime import datetime
import random

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WebScraper:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None

    async def setup(self):
        """Playwrightの初期化を確実に行う"""
        logger.info("Starting Playwright setup...")
        try:
            self._playwright = await async_playwright().start()
            logger.info("Launching browser...")
            
            launch_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu'
            ]

            self._browser = await self._playwright.firefox.launch(
                headless=True,
                args=launch_args,
                firefox_user_prefs={
                    "media.navigator.enabled": False,
                    "media.peerconnection.enabled": False
                }
            )

            logger.info("Creating browser context...")
            self._context = await self._browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/121.0',
                bypass_csp=True,
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                }
            )

            logger.info("Creating new page...")
            self._page = await self._context.new_page()
            await self._page.set_default_timeout(30000)
            await self._page.set_default_navigation_timeout(30000)

            await self._context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            """)

            logger.info("Playwright setup completed successfully")
            return True

        except Exception as e:
            logger.error(f"Error during setup: {e}")
            await self.cleanup()
            return False

    async def cleanup(self):
        """リソースの確実な解放"""
        logger.info("Starting cleanup...")
        try:
            if self._page:
                await self._page.close()
                self._page = None

            if self._context:
                await self._context.close()
                self._context = None

            if self._browser:
                await self._browser.close()
                self._browser = None

            if self._playwright:
                await self._playwright.stop()
                self._playwright = None

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        
        logger.info("Cleanup completed")

    async def scrape_page(self, url: str) -> str:
        """ページのスクレイピング"""
        if not self._page:
            raise Exception("Page is not initialized")

        try:
            logger.info(f"Navigating to {url}")
            await asyncio.sleep(random.uniform(2, 4))

            response = await self._page.goto(
                url,
                wait_until='networkidle',
                timeout=60000
            )

            if not response:
                raise Exception("Failed to get page response")

            if response.status >= 400:
                raise Exception(f"Error status code: {response.status}")

            await asyncio.sleep(random.uniform(3, 5))
            
            # モバイルスクロールのシミュレーション
            await self._page.evaluate("""
                window.scrollBy({
                    top: document.body.scrollHeight,
                    behavior: 'smooth'
                });
            """)
            
            await asyncio.sleep(random.uniform(2, 4))

            html = await self._page.content()
            return html

        except Exception as e:
            logger.error(f"Error scraping page: {e}")
            raise

    async def save_page(self, url: str, output_dir: str = 'sites') -> bool:
        try:
            if not await self.setup():
                raise Exception("Failed to setup Playwright")

            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            domain_dir = os.path.join(output_dir, domain)
            os.makedirs(domain_dir, exist_ok=True)

            html_content = await self.scrape_page(url)
            if not html_content:
                raise Exception("No content retrieved")

            # HTMLの整形とリソースURLの修正
            soup = BeautifulSoup(html_content, 'html.parser')
            for tag in soup.find_all(['img', 'video', 'iframe', 'source', 'link', 'script']):
                for attr in ['src', 'href', 'data-src']:
                    if tag.get(attr):
                        tag[attr] = urljoin(url, tag[attr])

            filename = "index.html" if parsed_url.path.strip('/') == "" else parsed_url.path.strip('/').replace('/', '_') + ".html"
            filepath = os.path.join(domain_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(str(soup))

            logger.info(f"Page saved successfully to {filepath}")
            return True

        except Exception as e:
            logger.error(f"Error saving page: {e}")
            return False

        finally:
            await self.cleanup()

async def main():
    if len(sys.argv) != 2:
        logger.error("Usage: python scraper.py <url>")
        return 1

    url = sys.argv[1]
    logger.info(f"Starting scraper for URL: {url}")
    
    try:
        scraper = WebScraper(url)
        success = await scraper.save_page(url)
        return 0 if success else 1
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
