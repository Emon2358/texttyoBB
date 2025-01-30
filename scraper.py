import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
import json
import re
import logging
from datetime import datetime
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import chromedriver_autoinstaller  # ChromeDriver を自動インストール

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebScraper:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = None
        self.url_patterns = {}
        self.driver = None
        self.load_url_patterns()
        self.setup_selenium()

    def setup_selenium(self):
        """ChromeDriver を自動インストールし、Selenium WebDriver をセットアップ"""
        chromedriver_autoinstaller.install()  # ChromeDriver の自動インストール
        chrome_options = Options()
        chrome_options.add_argument("--headless")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")

        self.driver = webdriver.Chrome(options=chrome_options)
        self.driver.set_page_load_timeout(30)

    def cleanup(self):
        """リソースの後処理"""
        if self.driver:
            self.driver.quit()

    def load_url_patterns(self):
        """URL パターンを JSON ファイルから読み込む"""
        if os.path.exists('url_patterns.json'):
            with open('url_patterns.json', 'r') as f:
                self.url_patterns = json.load(f)

    def save_url_patterns(self):
        """URL パターンを JSON ファイルに保存"""
        with open('url_patterns.json', 'w') as f:
            json.dump(self.url_patterns, f, indent=2)

    async def scrape_page(self, url: str) -> str:
        """Selenium を使ってページをスクレイピング"""
        try:
            self.driver.get(url)
            time.sleep(5)  # JavaScript 実行のための待機
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')

            # 画像、動画、スクリプト、スタイルシートなどの URL を元のドメインのまま保持
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
            self.cleanup()

if __name__ == "__main__":
    import sys
    url = sys.argv[1]
    scraper = WebScraper(url)
    asyncio.run(scraper.save_page(url))
