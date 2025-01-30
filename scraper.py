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
                '--headless=new',
                '--disable-web-security',
                '--disable-features=IsolateOrigins,site-per-process'
            ]

            self._browser = await self._playwright.firefox.launch(
                headless=True,
                args=launch_args,
                timeout=90000,
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
                viewport={'width': 390, 'height': 844},  # iPhoneに近いビューポート
                user_agent='Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1',
                bypass_csp=True,
                accept_downloads=False
            )
            
            # JavaScriptを有効化
            await self._context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
            """)
            
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

                # タイムアウトとリクエストの設定
                self._page.set_default_timeout(90000)
                self._page.set_default_navigation_timeout(90000)
                
                # リクエストの監視を設定
                async def log_request(request):
                    logger.debug(f"Request: {request.method} {request.url}")
                self._page.on("request", log_request)
                
                logger.info("セットアップが正常に完了")
                return True
            return False

        except Exception as e:
            logger.error(f"セットアップ中にエラーが発生: {str(e)}")
            await self.cleanup()
            return False

    async def wait_for_content(self) -> bool:
        """ページのコンテンツが読み込まれるのを待機"""
        try:
            # DOMの読み込み完了を待機
            await self._page.wait_for_load_state('domcontentloaded')
            
            # ネットワークのアイドル状態を待機
            await self._page.wait_for_load_state('networkidle')
            
            # プレーヤーの要素が表示されるのを待機
            try:
                await self._page.wait_for_selector('.playControls__elements', timeout=10000)
            except:
                logger.info("プレーヤー要素が見つかりませんでした")
            
            # 追加のスクロール処理
            await self._page.evaluate("""
                window.scrollTo({
                    top: document.body.scrollHeight,
                    behavior: 'smooth'
                });
            """)
            
            await asyncio.sleep(5)  # コンテンツの読み込みを待機
            
            return True
        except Exception as e:
            logger.error(f"コンテンツの待機中にエラー: {str(e)}")
            return False

    async def scrape_page(self, url: str) -> Optional[str]:
        """ページのスクレイピング処理"""
        if not self._page:
            logger.error("ページが初期化されていません")
            return None

        try:
            logger.info(f"{url} にアクセス中...")
            
            # ページに移動
            response = await self._page.goto(
                url,
                wait_until='domcontentloaded',
                timeout=90000
            )

            if not response:
                logger.error("ページの応答がありません")
                return None

            if response.status >= 400:
                logger.error(f"エラーステータス: {response.status}")
                return None

            # コンテンツの読み込みを待機
            if not await self.wait_for_content():
                logger.error("コンテンツの読み込みに失敗")
                return None

            # ページのHTMLを取得
            content = await self._page.content()
            
            if not content:
                logger.error("HTMLコンテンツが空です")
                return None
                
            logger.info("ページのコンテンツを取得しました")
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
            
            # メタ情報の追加
            meta_time = soup.new_tag('meta')
            meta_time['name'] = 'scraping-time'
            meta_time['content'] = datetime.now().isoformat()
            soup.head.append(meta_time)
            
            # リソースのURL修正
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
