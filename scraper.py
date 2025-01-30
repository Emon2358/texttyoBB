# scraper.py
import asyncio
from playwright.async_api import async_playwright, Playwright
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
        self.playwright: Playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.url_patterns = {}
        self.load_url_patterns()

    def load_url_patterns(self):
        if os.path.exists('url_patterns.json'):
            with open('url_patterns.json', 'r') as f:
                self.url_patterns = json.load(f)

    async def setup(self):
        """Playwrightの初期化を確実に行う"""
        logger.info("Starting Playwright setup...")
        try:
            # Playwrightの起動
            self.playwright = await async_playwright().start()
            if not self.playwright:
                raise Exception("Failed to start Playwright")

            logger.info("Launching browser...")
            # ブラウザの起動
            self.browser = await self.playwright.firefox.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage'
                ]
            )
            if not self.browser:
                raise Exception("Failed to launch browser")

            logger.info("Creating browser context...")
            # コンテキストの作成
            self.context = await self.browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/121.0',
                bypass_csp=True,
                extra_http_headers={
                    'Accept-Language': 'en-US,en;q=0.9',
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
                }
            )
            if not self.context:
                raise Exception("Failed to create browser context")

            logger.info("Creating new page...")
            # 新しいページの作成
            self.page = await self.context.new_page()
            if not self.page:
                raise Exception("Failed to create new page")

            # 基本的なタイムアウト設定
            await self.page.set_default_timeout(30000)
            await self.page.set_default_navigation_timeout(30000)

            # JavaScript injection
            await self.context.add_init_script("""
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
            if self.page:
                logger.info("Closing page...")
                await self.page.close()
                self.page = None

            if self.context:
                logger.info("Closing context...")
                await self.context.close()
                self.context = None

            if self.browser:
                logger.info("Closing browser...")
                await self.browser.close()
                self.browser = None

            if self.playwright:
                logger.info("Stopping Playwright...")
                await self.playwright.stop()
                self.playwright = None

        except Exception as e:
            logger.error(f"Error during cleanup: {e}")
        finally:
            logger.info("Cleanup completed")

    async def scrape_page(self, url: str) -> str:
        """ページのスクレイピング"""
        try:
            logger.info(f"Navigating to {url}")
            # ページの読み込み
            response = await self.page.goto(url, wait_until='networkidle')
            if not response:
                raise Exception("Failed to get page response")

            if response.status >= 400:
                raise Exception(f"Error status code: {response.status}")

            # ランダムな待機と操作
            await asyncio.sleep(random.uniform(3, 5))
            
            # スクロールシミュレーション
            await self.page.evaluate("""
                window.scrollTo({
                    top: document.body.scrollHeight / 2,
                    behavior: 'smooth'
                });
            """)
            
            await asyncio.sleep(random.uniform(2, 4))

            # コンテンツの取得
            html = await self.page.content()
            soup = BeautifulSoup(html, 'html.parser')

            # URLの修正
            for tag in soup.find_all(['img', 'video', 'iframe', 'source', 'link', 'script']):
                for attr in ['src', 'href', 'data-src']:
                    if tag.get(attr):
                        tag[attr] = urljoin(url, tag[attr])

            logger.info("Page scraped successfully")
            return str(soup)

        except Exception as e:
            logger.error(f"Error scraping page: {e}")
            raise

    async def save_page(self, url: str, output_dir: str = 'sites') -> bool:
        """ページの保存"""
        try:
            # Playwrightのセットアップ
            setup_success = await self.setup()
            if not setup_success:
                raise Exception("Failed to setup Playwright")

            # 保存ディレクトリの準備
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            domain_dir = os.path.join(output_dir, domain)
            os.makedirs(domain_dir, exist_ok=True)

            # スクレイピングの実行
            html_content = await self.scrape_page(url)
            if not html_content:
                raise Exception("No content retrieved")

            # ファイルの保存
            filename = "index.html" if parsed_url.path.strip('/') == "" else parsed_url.path.strip('/').replace('/', '_') + ".html"
            filepath = os.path.join(domain_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)

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
    
    scraper = WebScraper(url)
    success = await scraper.save_page(url)
    
    return 0 if success else 1

if __name__ == "__main__":
    try:
        exit_code = asyncio.run(main())
        sys.exit(exit_code)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        sys.exit(1)
