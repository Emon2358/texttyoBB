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
        self.browser = None
        self.context = None
        self.page = None
        self.url_patterns = {}
        self.load_url_patterns()

    def load_url_patterns(self):
        """URL パターンを JSON ファイルから読み込む"""
        if os.path.exists('url_patterns.json'):
            with open('url_patterns.json', 'r') as f:
                self.url_patterns = json.load(f)

    def save_url_patterns(self):
        """URL パターンを JSON ファイルに保存"""
        with open('url_patterns.json', 'w') as f:
            json.dump(self.url_patterns, f, indent=2)

    async def init_playwright(self):
        """Playwrightの初期化とブラウザの設定"""
        playwright = await async_playwright().start()
        
        # ブラウザの起動（Firefox使用）
        self.browser = await playwright.firefox.launch(
            headless=True if os.environ.get('CI') else False
        )

        # コンテキストの作成（様々な回避設定を含む）
        self.context = await self.browser.new_context(
            viewport={'width': 1920, 'height': 1080},
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/121.0',
            java_script_enabled=True,
            bypass_csp=True,  # Content Security Policyをバイパス
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
            }
        )

        # JavaScript指紋対策
        await self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
            Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
        """)

        self.page = await self.context.new_page()
        
        # ネットワークアイドル状態を待つための設定
        await self.page.set_default_navigation_timeout(30000)
        await self.page.set_default_timeout(30000)

    async def scrape_page(self, url: str) -> str:
        """改善されたページスクレイピング処理"""
        try:
            # ランダムな遅延
            await asyncio.sleep(random.uniform(2, 5))

            # ページへの移動とロード待ち
            await self.page.goto(url, wait_until='networkidle')
            
            # SoundCloud固有の要素の待機
            try:
                await self.page.wait_for_selector('.soundTitle__usernameTitleContainer', timeout=10000)
                logger.info("Found SoundCloud specific elements")
            except:
                logger.info("Could not find SoundCloud specific elements, continuing anyway...")

            # さらなるインタラクションのシミュレーション
            await self.page.mouse.move(random.randint(100, 500), random.randint(100, 500))
            await self.page.mouse.wheel(delta_y=random.randint(100, 300))
            await asyncio.sleep(random.uniform(1, 3))

            # ページコンテンツの取得
            html = await self.page.content()
            soup = BeautifulSoup(html, 'html.parser')
            
            # リソースURLの修正
            for tag in soup.find_all(['img', 'video', 'iframe', 'source', 'link', 'script']):
                if tag.get('src'):
                    tag['src'] = urljoin(url, tag['src'])
                if tag.get('href'):
                    tag['href'] = urljoin(url, tag['href'])
                if tag.get('data-src'):
                    tag['data-src'] = urljoin(url, tag['data-src'])

            return str(soup)
            
        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return ""

    async def save_page(self, url: str, output_dir: str = 'sites'):
        """スクレイピングしたページを保存"""
        try:
            await self.init_playwright()
            
            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            domain_dir = os.path.join(output_dir, domain)
            os.makedirs(domain_dir, exist_ok=True)

            html_content = await self.scrape_page(url)
            if not html_content:
                return

            filename = "index.html" if parsed_url.path.strip('/') == "" else parsed_url.path.strip('/').replace('/', '_') + ".html"
            filepath = os.path.join(domain_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"Saved page to {filepath}")
            return filepath
            
        finally:
            if self.browser:
                await self.browser.close()

async def main(url):
    scraper = WebScraper(url)
    await scraper.save_page(url)

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python scraper.py <url>")
        sys.exit(1)
        
    url = sys.argv[1]
    asyncio.run(main(url))
