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
import urllib.parse
import sys

# Selenium関連のインポート
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager

# スクレイピング出力ディレクトリをコマンドライン引数から受け取る
OUTPUT_DIR = sys.argv[-1] if len(sys.argv) > 2 else 'pages'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebScraper:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.url_patterns = self.load_url_patterns()
        self.driver = self._setup_selenium_driver()

    def load_url_patterns(self):
        """URL パターンの設定をJSONから読み込む"""
        try:
            if os.path.exists('url_patterns.json'):
                with open('url_patterns.json', 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.warning(f"Error loading URL patterns: {e}")
            return {}

    def save_url_patterns(self):
        """URL パターンの設定をJSONに保存"""
        try:
            with open('url_patterns.json', 'w') as f:
                json.dump(self.url_patterns, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving URL patterns: {e}")

    def update_url_pattern(self, old_url: str, new_url: str):
        """新しいURLパターンを登録"""
        try:
            old_parsed = urlparse(old_url)
            new_parsed = urlparse(new_url)
            
            # パスのパターンを抽出
            old_path = old_parsed.path
            new_path = new_parsed.path
            
            # 日付やIDなどの可変部分をパターン化
            pattern = self.create_url_pattern(old_path, new_path)
            self.url_patterns[pattern] = {
                'example_old': old_url,
                'example_new': new_url,
                'last_updated': datetime.now().isoformat()
            }
            self.save_url_patterns()
        except Exception as e:
            logger.error(f"Error updating URL pattern: {e}")

    def create_url_pattern(self, old_path: str, new_path: str) -> str:
        """URLのパターンを生成"""
        try:
            parts_old = old_path.split('/')
            parts_new = new_path.split('/')
            
            pattern_parts = []
            for old, new in zip(parts_old, parts_new):
                if old == new:
                    pattern_parts.append(old)
                else:
                    # 数字のみの部分は {id} として扱う
                    if old.isdigit() and new.isdigit():
                        pattern_parts.append('{id}')
                    # 日付パターンの検出
                    elif re.match(r'\d{4}-\d{2}-\d{2}', old) and re.match(r'\d{4}-\d{2}-\d{2}', new):
                        pattern_parts.append('{date}')
                    else:
                        pattern_parts.append('*')
            
            return '/'.join(pattern_parts)
        except Exception as e:
            logger.error(f"Error creating URL pattern: {e}")
            return '*'

    def _setup_selenium_driver(self):
        """Seleniumのヘッドレスブラウザを設定"""
        try:
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

            return webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        except Exception as e:
            logger.error(f"Error setting up Selenium driver: {e}")
            return None

    def _get_site_name(self, url: str) -> str:
        """URLからサイト名を取得"""
        parsed_url = urllib.parse.urlparse(url)
        
        # ドメイン名から不要な部分を削除
        domain = parsed_url.netloc
        domain = domain.replace('www.', '')
        domain = domain.split('.')[0]  # 第一レベルドメインを取得
        
        # タイトルからサイト名を取得（可能な場合）
        try:
            title = self.driver.title
            if title:
                # タイトルが存在する場合は、それを優先
                site_name = re.sub(r'[^\w\-_\.]', '_', title)[:50]
                return site_name
        except:
            pass
        
        # ドメイン名をサイト名として使用
        return re.sub(r'[^\w\-_\.]', '_', domain)[:50]

    async def save_page(self, url: str, output_dir: str = OUTPUT_DIR):
        """ページを保存する高度な実装"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            
            # ページコンテンツを取得
            html_content = await self.scrape_page(url)
            
            if not html_content:
                logger.warning(f"No content retrieved for {url}")
                return None
            
            # サイト名を取得
            site_name = self._get_site_name(url)
            
            # ファイル名生成
            parsed_url = urlparse(url)
            filename_base = re.sub(r'[^a-zA-Z0-9]', '_', parsed_url.path or 'index')
            filename = f"{site_name}_{filename_base}_{int(datetime.now().timestamp())}.html"
            
            # ファイルパス
            filepath = os.path.join(output_dir, filename)
            
            # メタデータ保存
            metadata = {
                'original_url': url,
                'site_name': site_name,
                'scraped_at': datetime.now().isoformat(),
                'domain': parsed_url.netloc
            }
            
            # ファイル書き込み
            with open(filepath,  'w', encoding='utf-8') as f:
                f.write(html_content)
            
            # メタデータ保存
            with open(f"{filepath}.json", 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info(f"Successfully saved page from {url}")
            return filepath
        
        except Exception as e:
            logger.error(f"Error saving page from {url}: {e}")
            return None

    async def scrape_page(self, url: str) -> str:
        """高度なページスクレイピング"""
        try:
            # Seleniumを使用してページを読み込む
            if not self.driver:
                logger.error("Selenium driver not initialized")
                return ""
            
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
                        # 元のURLを保持するために、元のドメインを使用
                        tag[attr] = urljoin(url, tag[attr])
            
            # スクリプトタグ内のコンテンツを削除（セキュリティとパフォーマンス上の理由）
            for script in soup(["script", "style"]):
                script.decompose()
            
            return str(soup)
        
        except Exception as e:
            logger.error(f"Advanced scraping error for {url}: {e}")
            return ""

    def close_driver(self):
        """Seleniumドライバーを閉じる"""
        if self.driver:
            self.driver.quit()

async def main(urls):
    tasks = []
    scrapers = []
    
    try:
        for url in urls:
            scraper = WebScraper(url)
            scrapers.append(scraper)
            task = asyncio.create_task(scraper.save_page(url))
            tasks.append(task)
        
        # タスクの実行と結果の取得
        results = await asyncio.gather(*tasks)
        
        return results
    
    except Exception as e:
        logger.error(f"Error in main scraping process: {e}")
        return None
    
    finally:
        # すべてのScraperのドライバーを閉じる
        for scraper in scrapers:
            scraper.close_driver()

if __name__ == "__main__":
    # ロギングの設定をさらに詳細に
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('scraper.log', encoding='utf-8')
        ]
    )
    
    # コマンドライン引数のチェック
    if len(sys.argv) < 2:
        print("Usage: python scraper.py <url1> <url2> ...")
        sys.exit(1)
    
    # スクレイピングするURLのリスト
    urls = sys.argv[1:]
    
    try:
        # asyncioを使用してスクレイピングを実行
        results = asyncio.run(main(urls))
        
        # 結果の表示
        if results:
            for result in results:
                if result:
                    print(f"Successfully scraped: {result}")
                else:
                    print("Failed to scrape a URL")
        else:
            print("No URLs were scraped successfully")
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)
