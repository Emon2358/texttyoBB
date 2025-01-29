import requests
from bs4 import BeautifulSoup
import os
import urllib.parse
from urllib.parse import urljoin
import mimetypes
import re

class WebScraper:
    def __init__(self, base_url):
        self.base_url = base_url
        self.visited_urls = set()
        self.session = requests.Session()
        self.output_dir = "site"

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
        # Update links
        for tag in soup.find_all(['a', 'link', 'script', 'img']):
            for attr in ['href', 'src']:
                if tag.get(attr):
                    absolute_url = urljoin(current_url, tag[attr])
                    if self.base_url in absolute_url:
                        local_path = self.get_local_path(absolute_url)
                        tag[attr] = '/' + local_path
        return soup

    def get_local_path(self, url):
        """Convert URL to local file path"""
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.strip('/')
        if not path:
            path = 'index.html'
        elif not os.path.splitext(path)[1]:
            path = os.path.join(path, 'index.html')
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
