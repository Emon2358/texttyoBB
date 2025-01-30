# scraper.py

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
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
import chromedriver_autoinstaller
import random

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
        """より本物のブラウザに近い設定でSeleniumをセットアップ"""
        chromedriver_autoinstaller.install()

        chrome_options = Options()
        
        # 一般的なブラウザの設定
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--disable-blink-features=AutomationControlled')
        chrome_options.add_argument('--disable-infobars')
        chrome_options.add_argument('--disable-notifications')
        
        # 一般的なUser-Agentを設定
        chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        # その他の必要な設定
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument("--disable-gpu")
        
        # ヘッドレスモードの設定（必要な場合）
        if os.environ.get('CI'):  # CI環境の場合のみヘッドレスモード
            chrome_options.add_argument('--headless=new')

        # Webdriver設定の追加
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)

        self.driver = webdriver.Chrome(options=chrome_options)
        
        # JavaScriptの実行
        self.driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # タイムアウトの設定
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
        """改善されたページスクレイピング処理"""
        try:
            # ランダムな遅延を追加
            time.sleep(random.uniform(2, 5))
            
            self.driver.get(url)
            
            # ページの読み込みを待機
            wait = WebDriverWait(self.driver, 20)
            
            # SoundCloud固有の要素を待機
            try:
                # プレーヤーやトラック情報などの要素を待機
                wait.until(EC.presence_of_element_located((By.CLASS_NAME, "soundTitle__usernameTitleContainer")))
                logger.info("Found SoundCloud specific elements")
            except:
                logger.info("Could not find SoundCloud specific elements, continuing anyway...")
            
            # さらに短い待機を追加
            time.sleep(random.uniform(3, 5))
            
            html = self.driver.page_source
            soup = BeautifulSoup(html, 'html.parser')
            
            # 元のリソースURLを維持
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

            # ファイル名の生成
            filename = "index.html" if parsed_url.path.strip('/') == "" else parsed_url.path.strip('/').replace('/', '_') + ".html"
            filepath = os.path.join(domain_dir, filename)

            # ページの保存
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            logger.info(f"Saved page to {filepath}")
            return filepath
        finally:
            self.cleanup()

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python scraper.py <url>")
        sys.exit(1)
        
    url = sys.argv[1]
    scraper = WebScraper(url)
    asyncio.run(scraper.save_page(url))
