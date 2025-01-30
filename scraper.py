import asyncio
from playwright.async_api import async_playwright, Browser, BrowserContext, Page
from bs4 import BeautifulSoup
from urllib.parse import urljoin, urlparse
import os
import json
import logging
import sys
from datetime import datetime
import random
from typing import Optional

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WebScraper:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self._playwright = None
        self._browser: Optional[Browser] = None
        self._context: Optional[BrowserContext] = None
        self._page: Optional[Page] = None

    async def _init_browser(self) -> bool:
        """ブラウザの初期化を行う"""
        try:
            launch_args = [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-accelerated-2d-canvas',
                '--disable-gpu',
                '--headless=new'  # 新しいヘッドレスモードを使用
            ]

            self._browser = await self._playwright.firefox.launch(
                headless=True,
                args=launch_args,
                timeout=60000,
            )
            return True
        except Exception as e:
            logger.error(f"ブラウザの初期化に失敗: {str(e)}")
            return False

    async def _init_context(self) -> bool:
        """ブラウザコンテキストの初期化を行う"""
        try:
            if not self._browser:
                return False

            self._context = await self._browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) Firefox/121.0',
                bypass_csp=True
            )
            return True
        except Exception as e:
            logger.error(f"コンテキストの初期化に失敗: {str(e)}")
            return False

    async def setup(self) -> bool:
        """Playwrightの初期化処理"""
        logger.info("Playwright のセットアップを開始...")
        try:
            if self._playwright is None:
                self._playwright = await async_playwright().start()

            if not self._playwright:
                raise Exception("Playwright の起動に失敗")

            logger.info("ブラウザを起動中...")
            if not await self._init_browser():
                raise Exception("ブラウザの初期化に失敗")

            logger.info("ブラウザコンテキストを作成中...")
            if not await self._init_context():
                raise Exception("コンテキストの初期化に失敗")

            logger.info("ページを作成中...")
            if self._context:
                self._page = await self._context.new_page()
                if not self._page:
                    raise Exception("ページの作成に失敗")

                # タイムアウトの設定
                self._page.set_default_timeout(60000)
                self._page.set_default_navigation_timeout(60000)
                
                logger.info("セットアップが正常に完了")
                return True
            return False

        except Exception as e:
            logger.error(f"セットアップ中にエラーが発生: {str(e)}")
            await self.cleanup()
            return False

    async def cleanup(self):
        """リソースの解放処理"""
        logger.info("クリーンアップを開始...")
        try:
            if self._page:
                logger.info("ページを閉じています...")
                await self._page.close()
                self._page = None

            if self._context:
                logger.info("コンテキストを閉じています...")
                await self._context.close()
                self._context = None

            if self._browser:
                logger.info("ブラウザを閉じています...")
                await self._browser.close()
                self._browser = None

            if self._playwright:
                logger.info("Playwright を停止しています...")
                await self._playwright.stop()
                self._playwright = None

        except Exception as e:
            logger.error(f"クリーンアップ中にエラーが発生: {str(e)}")
        finally:
            logger.info("クリーンアップ完了")

    async def scrape_page(self, url: str) -> Optional[str]:
        """ページのスクレイピング処理"""
        if not self._page:
            logger.error("ページが初期化されていません")
            return None

        try:
            logger.info(f"{url} にアクセス中...")
            await asyncio.sleep(random.uniform(2, 4))

            response = await self._page.goto(
                url,
                wait_until='networkidle',
                timeout=60000
            )

            if not response:
                logger.error("ページの応答がありません")
                return None

            if response.status >= 400:
                logger.error(f"エラーステータス: {response.status}")
                return None

            await asyncio.sleep(random.uniform(3, 5))
            
            # JavaScriptの実行を待機
            await self._page.wait_for_load_state('domcontentloaded')
            await self._page.wait_for_load_state('networkidle')
            
            # スクロール処理
            await self._page.evaluate("""
                window.scrollBy({
                    top: document.body.scrollHeight,
                    behavior: 'smooth'
                });
            """)
            
            await asyncio.sleep(random.uniform(2, 4))
            
            content = await self._page.content()
            return content

        except Exception as e:
            logger.error(f"スクレイピング中にエラーが発生: {str(e)}")
            return None

    async def save_page(self, url: str, output_dir: str = 'sites') -> bool:
        """ページの保存処理"""
        try:
            if not await self.setup():
                raise Exception("Playwright のセットアップに失敗")

            parsed_url = urlparse(url)
            domain = parsed_url.netloc
            domain_dir = os.path.join(output_dir, domain)
            os.makedirs(domain_dir, exist_ok=True)

            html_content = await self.scrape_page(url)
            if not html_content:
                raise Exception("コンテンツの取得に失敗")

            # HTML の整形処理
            soup = BeautifulSoup(html_content, 'html.parser')
            for tag in soup.find_all(['img', 'video', 'iframe', 'source', 'link', 'script']):
                for attr in ['src', 'href', 'data-src']:
                    if tag.get(attr):
                        tag[attr] = urljoin(url, tag[attr])

            filename = "index.html" if parsed_url.path.strip('/') == "" else parsed_url.path.strip('/').replace('/', '_') + ".html"
            filepath = os.path.join(domain_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(str(soup))

            logger.info(f"ページを {filepath} に保存しました")
            return True

        except Exception as e:
            logger.error(f"ページの保存中にエラーが発生: {str(e)}")
            return False

        finally:
            await self.cleanup()

async def main():
    if len(sys.argv) != 2:
        logger.error("使用方法: python scraper.py <url>")
        return 1

    url = sys.argv[1]
    logger.info(f"スクレイピングを開始: {url}")
    
    try:
        scraper = WebScraper(url)
        success = await scraper.save_page(url)
        return 0 if success else 1
    except Exception as e:
        logger.error(f"致命的なエラーが発生: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
