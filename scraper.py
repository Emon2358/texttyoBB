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
                '--disable-features=IsolateOrigins,site-per-process',
                '--window-size=1920,1080'  # デスクトップサイズのウィンドウ
            ]

            self._browser = await self._playwright.chromium.launch(  # Firefoxからより一般的なChromiumに変更
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
                viewport={'width': 1920, 'height': 1080},  # デスクトップサイズのビューポート
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',  # デスクトップのUser-Agent
                bypass_csp=True,
                accept_downloads=True  # デスクトップではダウンロードを許可
            )
            
            # Webdriverの検出を回避
            await self._context.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                
                // プラットフォーム情報をデスクトップに設定
                Object.defineProperty(navigator, 'platform', {
                    get: () => 'Win32'
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

                self._page.set_default_timeout(90000)
                self._page.set_default_navigation_timeout(90000)
                
                # デスクトップ向けのイベントリスナーを追加
                async def handle_dialog(dialog):
                    await dialog.dismiss()
                self._page.on('dialog', handle_dialog)
                
                async def log_request(request):
                    logger.debug(f"Request: {request.method} {request.url}")
                self._page.on("request", log_request)
                
                logger.info("セットアップが正常に完了")
                return True
            return False

        except Exception as e:
            logger.error(f"セットアップ中にエラーが発生: {str(e)}")
            await self._cleanup()
            return False

    async def wait_for_content(self) -> bool:
        try:
            await self._page.wait_for_load_state('domcontentloaded')
            await self._page.wait_for_load_state('networkidle')
            
            # スクロール処理を改善（デスクトップ向け）
            await self._page.evaluate("""
                const scroll = async () => {
                    const distance = 100;
                    const delay = 100;
                    while (window.scrollY + window.innerHeight < document.documentElement.scrollHeight) {
                        window.scrollBy(0, distance);
                        await new Promise(resolve => setTimeout(resolve, delay));
                    }
                }
                scroll();
            """)
            
            await asyncio.sleep(3)  # スクロール完了を待機
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

            if not await self.wait_for_content():
                logger.error("コンテンツの読み込みに失敗")
                return None

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
        success = False
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

            soup = BeautifulSoup(html_content, 'html.parser')
            
            meta_time = soup.new_tag('meta')
            meta_time['name'] = 'scraping-time'
            meta_time['content'] = datetime.now().isoformat()
            if soup.head:
                soup.head.append(meta_time)
            else:
                head = soup.new_tag('head')
                head.append(meta_time)
                soup.html.insert(0, head)
            
            # デスクトップ向けのリソースパス修正
            for tag in soup.find_all(['img', 'video', 'iframe', 'source', 'link', 'script']):
                for attr in ['src', 'href', 'data-src', 'srcset']:
                    if tag.get(attr):
                        if attr == 'srcset':
                            sources = tag[attr].split(',')
                            new_sources = []
                            for source in sources:
                                parts = source.strip().split()
                                if len(parts) >= 1:
                                    parts[0] = urljoin(url, parts[0])
                                    new_sources.append(' '.join(parts))
                            tag[attr] = ', '.join(new_sources)
                        else:
                            tag[attr] = urljoin(url, tag[attr])

            filename = "index.html" if parsed_url.path.strip('/') == "" else parsed_url.path.strip('/').replace('/', '_') + ".html"
            filepath = os.path.join(domain_dir, filename)

            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(str(soup))

            logger.info(f"ページを {filepath} に保存しました")
            success = True
            return True

        except Exception as e:
            logger.error(f"ページの保存中にエラーが発生: {str(e)}")
            return False

        finally:
            await self._cleanup()
            if not success:
                logger.error("スクレイピングは失敗しました")

async def main():
    if len(sys.argv) != 2:
        logger.error("使用方法: python scraper.py <url>")
        return 1

    url = sys.argv[1]
    logger.info(f"スクレイピングを開始: {url}")
    
    scraper = WebScraper(url)
    try:
        success = await scraper.save_page(url)
        return 0 if success else 1
    except Exception as e:
        logger.error(f"致命的なエラーが発生: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
