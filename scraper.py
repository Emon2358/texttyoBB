import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
import json
import re
import logging
from datetime import datetime
import random

# Selenium関連のインポート
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebScraper:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.url_patterns = {}
        self.load_url_patterns()
        self.driver = self._setup_selenium_driver()

    def _setup_selenium_driver(self):
        """Seleniumのヘッドレスブラウザを設定"""
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # ヘッドレスモード
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--remote-debugging-port=9222")
        
        # ユーザーエージェントをランダムに設定
        user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36"
        ]
        chrome_options.add_argument(f"user-agent={random.choice(user_agents)}")

        # プロキシ設定（オプション）
        # chrome_options.add_argument(f'--proxy-server={proxy}')

        return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)

    async def scrape_page(self, url: str) -> str:
        """高度なページスクレイピング"""
        try:
            # Seleniumを使用してページを読み込む
            self.driver.get(url)
            
            # ページが完全に読み込まれるまで待機
            await asyncio.sleep(3)  # 必要に応じて調整
            
            # JavaScript実行後のソースを取得
            html = self.driver.page_source
            
            soup = BeautifulSoup(html, 'html.parser')
            
            # リソースのURL正規化
            for tag in soup.find_all(['img', 'video', 'iframe', 'source', 'link', 'script']):
                for attr in ['src', 'href', 'data-src']:
                    if tag.get(attr):
                        tag[attr] = urljoin(url, tag[attr])
            
            # スクリプトタグ内のコンテンツを削除（セキュリティとパフォーマンス上の理由）
            for script in soup(["script", "style"]):
                script.decompose()
            
            return str(soup)
        
        except Exception as e:
            logger.error(f"Advanced scraping error for {url}: {e}")
            return ""

    async def save_page(self, url: str, output_dir: str = 'pages'):
        """ページを保存する高度な実装"""
        os.makedirs(output_dir, exist_ok=True)
        
        try:
            # ページコンテンツを取得
            html_content = await self.scrape_page(url)
            
            if not html_content:
                logger.warning(f"No content retrieved for {url}")
                return None
            
            # ファイル名生成
            parsed_url = urlparse(url)
            filename = re.sub(r'[^a-zA-Z0-9]', '_', parsed_url.path or 'index')
            filename = f"{filename}_{int(datetime.now().timestamp())}.html"
            
            # ファイルパス
            filepath = os.path.join(output_dir, filename)
            
            # メタデータ保存
            metadata = {
                'original_url': url,
                'scraped_at': datetime.now().isoformat(),
                'domain': parsed_url.netloc
            }
            
            # ファイル書き込み
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # メタデータ保存
            with open(f"{filepath}.json", 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Successfully saved page from {url}")
            return filepath
        
        except Exception as e:
            logger.error(f"Error saving page from {url}: {e}")
            return None

    def __del__(self):
        """クリーンアップ"""
        if hasattr(self, 'driver'):
            self.driver.quit()

async def main(urls):
    tasks = []
    for url in urls:
        scraper = WebScraper(url)
        task = asyncio.create_task(scraper.save_page(url))
        tasks.append(task)
    
    await asyncio.gather(*tasks)

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) < 2:
        print("Usage: python scraper.py <url1> <url2> ...")
        sys.exit(1)
    
    urls = sys.argv[1:]
    asyncio.run(main(urls))
