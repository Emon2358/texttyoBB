import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
from urllib.parse import urljoin
import mimetypes
import re

class WebScraper:
    def __init__(self, base_url):
        self.base_url = base_url.rstrip('/')
        self.visited_urls = set()
        self.session = requests.Session()
        self.output_dir = "site"
        # リポジトリ名を環境変数から取得（GitHub Actions環境用）
        self.repo_name = os.environ.get('GITHUB_REPOSITORY', '').split('/')[-1]

    def download_resource(self, url, local_path):
        """Download resources like images, CSS, JS files"""
        try:
            response = self.session.get(url)
            if response.status_code == 200:
                os.makedirs(os.path.dirname(local_path), exist_ok=True)
                with open(local_path, 'wb') as f:
                    f.write(response.content)
                return True
        except Exception as e:
            print(f"Error downloading {url}: {e}")
        return False

    def update_links(self, soup, current_url):
        """Update all links to point to local resources"""
        base_path = f'/{self.repo_name}' if self.repo_name else ''
        
        # Update links
        for tag in soup.find_all(['a', 'link', 'script', 'img']):
            for attr in ['href', 'src']:
                if tag.get(attr):
                    absolute_url = urljoin(current_url, tag[attr])
                    if self.base_url in absolute_url:
                        local_path = self.get_local_path(absolute_url)
                        # GitHub Pages用のパスに修正
                        tag[attr] = f'{base_path}/{local_path}'
                    elif tag[attr].startswith('/'):
                        # 絶対パスの場合もGitHub Pages用に修正
                        tag[attr] = f'{base_path}{tag[attr]}'

        # Base タグの追加
        base_tag = soup.find('base')
        if base_tag:
            base_tag['href'] = f'{base_path}/'
        else:
            new_base = soup.new_tag('base')
            new_base['href'] = f'{base_path}/'
            soup.head.insert(0, new_base)

        return soup

    def get_local_path(self, url):
        """Convert URL to local file path"""
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.strip('/')
        
        # パスが空の場合はindex.htmlを使用
        if not path:
            return 'index.html'
            
        # URLの末尾がスラッシュで終わる場合
        if url.endswith('/'):
            return os.path.join(path, 'index.html')
            
        # 拡張子がない場合
        if not os.path.splitext(path)[1]:
            return os.path.join(path, 'index.html')
            
        return path

    def save_page(self, url, content):
        """Save HTML content to file"""
        local_path = os.path.join(self.output_dir, self.get_local_path(url))
        os.makedirs(os.path.dirname(local_path), exist_ok=True)
        with open(local_path, 'w', encoding='utf-8') as f:
            f.write(str(content))

    def scrape(self, url):
        """Main scraping function"""
        if url in self.visited_urls or not url.startswith(self.base_url):
            return

        self.visited_urls.add(url)
        print(f"Scraping: {url}")

        try:
            response = self.session.get(url)
            if response.status_code != 200:
                return

            soup = BeautifulSoup(response.text, 'html.parser')
            
            # ページのエンコーディングを明示的に設定
            if not soup.find('meta', charset=True):
                charset_tag = soup.new_tag('meta')
                charset_tag['charset'] = 'utf-8'
                soup.head.insert(0, charset_tag)

            soup = self.update_links(soup, url)

            # Download resources
            for tag in soup.find_all(['link', 'script', 'img']):
                for attr in ['href', 'src']:
                    if tag.get(attr):
                        resource_url = urljoin(url, tag[attr])
                        if resource_url.startswith(self.base_url):
                            local_path = os.path.join(self.output_dir, self.get_local_path(resource_url))
                            self.download_resource(resource_url, local_path)

            # Save the page
            self.save_page(url, soup.prettify())

            # Find and scrape all links
            for link in soup.find_all('a'):
                href = link.get('href')
                if href:
                    next_url = urljoin(url, href)
                    if next_url.startswith(self.base_url):
                        self.scrape(next_url)

        except Exception as e:
            print(f"Error scraping {url}: {e}")

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 2:
        print("Usage: python scraper.py <url>")
        sys.exit(1)
    
    target_url = sys.argv[1]
    scraper = WebScraper(target_url)
    scraper.scrape(target_url)
