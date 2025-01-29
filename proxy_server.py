import asyncio
import aiohttp
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
import json
import re
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class WebScraper:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.session = None
        self.url_patterns = {}
        self.load_url_patterns()

    def load_url_patterns(self):
        """URL パターンの設定をJSONから読み込む"""
        if os.path.exists('url_patterns.json'):
            with open('url_patterns.json', 'r') as f:
                self.url_patterns = json.load(f)

    def save_url_patterns(self):
        """URL パターンの設定をJSONに保存"""
        with open('url_patterns.json', 'w') as f:
            json.dump(self.url_patterns, f, indent=2)

    def update_url_pattern(self, old_url: str, new_url: str):
        """新しいURLパターンを登録"""
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

    def create_url_pattern(self, old_path: str, new_path: str) -> str:
        """URLのパターンを生成"""
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

    async def normalize_url(self, url: str) -> str:
        """URLを正規化して最新のパターンに変換"""
        parsed = urlparse(url)
        path = parsed.path
        
        for pattern, info in self.url_patterns.items():
            if self.match_pattern(path, pattern):
                return info['example_new']
        
        return url

    def match_pattern(self, path: str, pattern: str) -> bool:
        """パスがパターンにマッチするか確認"""
        pattern_parts = pattern.split('/')
        path_parts = path.split('/')
        
        if len(pattern_parts) != len(path_parts):
            return False
            
        for pattern_part, path_part in zip(pattern_parts, path_parts):
            if pattern_part in ['{id}', '{date}', '*']:
                continue
            if pattern_part != path_part:
                return False
        
        return True

    async def scrape_page(self, url: str) -> str:
        """ページをスクレイピングしてHTMLを生成"""
        async with aiohttp.ClientSession() as session:
            try:
                async with session.get(url) as response:
                    html = await response.text()
                    soup = BeautifulSoup(html, 'html.parser')
                    
                    # 画像、動画、iframeのsrcを元URLに置き換え
                    for tag in soup.find_all(['img', 'video', 'iframe', 'source']):
                        if tag.get('src'):
                            tag['src'] = urljoin(url, tag['src'])
                        if tag.get('data-src'):
                            tag['data-src'] = urljoin(url, tag['data-src'])
                    
                    # CSSとJavaScriptのリンクを元URLに置き換え
                    for tag in soup.find_all(['link', 'script']):
                        if tag.get('href'):
                            tag['href'] = urljoin(url, tag['href'])
                        if tag.get('src'):
                            tag['src'] = urljoin(url, tag['src'])
                    
                    return str(soup)
            except Exception as e:
                logger.error(f"Error scraping {url}: {e}")
                return ""

    async def save_page(self, url: str, output_dir: str = 'pages'):
        """ページをスクレイピングしてファイルに保存"""
        # 出力ディレクトリの作成
        os.makedirs(output_dir, exist_ok=True)
        
        # URLを正規化
        normalized_url = await self.normalize_url(url)
        
        # ページの内容を取得
        html_content = await self.scrape_page(normalized_url)
        if not html_content:
            return
        
        # ファイル名の生成
        parsed = urlparse(normalized_url)
        filename = re.sub(r'[^a-zA-Z0-9]', '_', parsed.path)
        if not filename:
            filename = 'index'
        filename = f"{filename}.html"
        
        # ファイルの保存
        filepath = os.path.join(output_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(html_content)
        
        logger.info(f"Saved page to {filepath}")
        return filepath

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 2:
        print("Usage: python scraper.py <url>")
        sys.exit(1)
    
    url = sys.argv[1]
    scraper = WebScraper(url)
    
    asyncio.run(scraper.save_page(url))
