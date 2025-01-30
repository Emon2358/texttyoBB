# scraper.py
import asyncio
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
import json
import logging
from datetime import datetime
import random

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebScraper:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.url_patterns = {}
        self.load_url_patterns()

    def load_url_patterns(self):
        if os.path.exists('url_patterns.json'):
            with open('url_patterns.json', 'r') as f:
                self.url_patterns = json.load(f)

    def save_url_patterns(self):
        with open('url_patterns.json', 'w') as f:
            json.dump(self.url_patterns, f, indent=2)

    async def init_playwright(self):
        """Playwrightの初期化とブラウザの設定を改善"""
        try:
            self.playwright = await async_playwright().start()
            
            # Firefoxブラウザを起動
            self.browser = await self.playwright.firefox.launch(
                headless=True,  # CI環境では常にheadlessモード
                args=['--no-sandbox']
            )

            # ブラウザコンテキストの作成
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/121.0',
                bypass_csp=True,
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1',
                }
            )

            # 新しいページを作成
            self.page = await self.context.new_page()

            # JavaScript指紋対策
            await self.context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
            """)

            if self.page:
                await self.page.set_default_navigation_timeout(30000)
                await self.page.set_default_timeout(30000)

            logger.info("Playwright initialized successfully")
            
        except Exception as e:
            logger.error(f"Error initializing Playwright: {e}")
            await self.cleanup()
            raise

    async def cleanup(self):
        """リソースの解放処理を改善"""
        try:
            if self.page:
                await self.page.close()
            if self.context:
                await self.context.close()
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()
        except Exception as e:
            logger.error(f"Error during cleanup: {e}")

    async def scrape_page(self, url: str) -> str:
        """改善されたスクレイピング処理"""
        try:
            logger.info(f"Starting to scrape: {url}")
            
            # ページへの移動とロード待ち
            response = await self.page.goto(url, wait_until='networkidle')
            if not response:
                logger.error("Failed to get response from page")
                return ""
            
            if response.status >= 400:
                logger.error(f"Error status code: {response.status}")
                return ""

            # ランダムな待機
            await asyncio.sleep(random.uniform(3, 5))

            # ユーザーインタラクションのシミュレーション
            await self.page.mouse.move(random.randint(100, 500), random.randint(100, 500))
            await self.page.mouse.wheel(delta_y=random.randint(100, 300))
            await asyncio.sleep(random.uniform(2, 4))

            # ページコンテンツの取得
            html = await self.page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # URLの修正
            for tag in soup.find_all(['img', 'video', 'iframe', 'source', 'link', 'script']):
                for attr in ['src', 'href', 'data-src']:
                    if tag.get(attr):
                        tag[attr] = urljoin(url, tag[attr])

            logger.info("Successfully scraped page")
            return str(soup)
            
        except Exception as e:
            logger.error(f"Error scraping page: {e}")
            return ""

    async def save_page(self, url: str, output_dir: str = 'sites'):
        """改善されたページ保存処理"""
        try:
            await self.init_playwright()
            
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            domain_dir = os.path.join(output_dir, domain)
            os.makedirs(domain_dir, exist_ok=True)

            html_content = await self.scrape_page(url)
            if not html_content:
                logger.error("No content to save")
                return

            filename = "index.html" if parsed_url.path.strip('/') == "" else parsed_url.path.strip('/').replace('/', '_') + ".html"
            filepath = os.path.join(domain_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"Successfully saved page to {filepath}")
            return filepath
            
        except Exception as e:
            logger.error(f"Error saving page: {e}")
            raise
        finally:
            await self.cleanup()

async def main():
    if len(sys.argv) != 2:
        print("Usage: python scraper.py <url>")
        return
    
    url = sys.argv[1]
    scraper = WebScraper(url)
    try:
        await scraper.save_page(url)
    except Exception as e:
        logger.error(f"Main error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    import sys
    asyncio.run(main())
