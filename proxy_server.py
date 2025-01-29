import asyncio
import aiohttp
from bs4 import BeautifulSoup
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import uvicorn
from urllib.parse import urljoin, urlparse, unquote
import re
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# CORSミドルウェアを追加
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ProxyServer:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.target_domain = None
        self.scheme = None
        self.base_url = None

    async def ensure_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    def set_target(self, url: str):
        parsed = urlparse(url)
        self.target_domain = parsed.netloc
        self.scheme = parsed.scheme
        self.base_url = f"{self.scheme}://{self.target_domain}"
        logger.info(f"Target set to: {self.base_url}")

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    def is_same_domain(self, url: str) -> bool:
        try:
            if not url:
                return False
            if url.startswith('//'):
                url = f"{self.scheme}:{url}"
            if url.startswith('/'):
                return True
            parsed = urlparse(url)
            return parsed.netloc == self.target_domain or not parsed.netloc
        except:
            return False

    async def modify_content(self, content: str, base_path: str) -> str:
        soup = BeautifulSoup(content, 'html.parser')

        # base要素の処理
        base_tag = soup.find('base')
        if base_tag:
            base_tag.decompose()

        # Update all links to go through our proxy
        for tag in soup.find_all(['a', 'link', 'script', 'img', 'form', 'iframe']):
            for attr in ['href', 'src', 'action']:
                if tag.get(attr):
                    url = tag[attr]
                    # データURLはスキップ
                    if url.startswith('data:'):
                        continue
                    # JavaScript URLはスキップ
                    if url.startswith('javascript:'):
                        continue
                    # 相対URLを絶対URLに変換
                    if url.startswith('//'):
                        url = f"{self.scheme}:{url}"
                    elif url.startswith('/'):
                        url = f"{self.base_url}{url}"
                    else:
                        url = urljoin(self.base_url, url)
                    
                    if self.is_same_domain(url):
                        parsed = urlparse(url)
                        path = parsed.path
                        if parsed.query:
                            path += f"?{parsed.query}"
                        tag[attr] = f"/{path.lstrip('/')}"

        # インラインスタイルの処理
        for tag in soup.find_all(style=True):
            style = tag['style']
            urls = re.findall(r'url\([\'"]?(.*?)[\'"]?\)', style)
            for url in urls:
                if url.startswith('/'):
                    style = style.replace(f"url({url})", f"url({self.base_url}{url})")
                    tag['style'] = style

        # スタイルタグの処理
        for style in soup.find_all('style'):
            if style.string:
                urls = re.findall(r'url\([\'"]?(.*?)[\'"]?\)', style.string)
                for url in urls:
                    if url.startswith('/'):
                        style.string = style.string.replace(
                            f"url({url})", f"url({self.base_url}{url})")

        return str(soup)

proxy_server = ProxyServer()

@app.on_event("startup")
async def startup_event():
    await proxy_server.ensure_session()

@app.on_event("shutdown")
async def shutdown_event():
    await proxy_server.close()

@app.get("/set-target")
async def set_target(url: str):
    proxy_server.set_target(url)
    logger.info(f"Target URL set to: {url}")
    return {"status": "success", "target": url}

@app.get("/")
async def root(request: Request):
    if not proxy_server.target_domain:
        return {"error": "Target not set. Please use /set-target?url=... first"}
    return await proxy("", request)

@app.get("/{path:path}")
async def proxy(path: str, request: Request):
    if not proxy_server.target_domain:
        return {"error": "Target not set. Please use /set-target?url=... first"}

    # ターゲットURLの構築
    target_url = f"{proxy_server.base_url}/{path}"
    if request.query_params:
        target_url += f"?{request.query_params}"

    logger.info(f"Proxying request to: {target_url}")

    try:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
        }
        
        async with proxy_server.session.get(target_url, headers=headers) as response:
            content_type = response.headers.get('Content-Type', '').split(';')[0]
            
            # バイナリレスポンスの処理
            if not content_type.startswith('text/') and \
               not content_type.startswith('application/javascript') and \
               not content_type.startswith('application/json'):
                return StreamingResponse(
                    response.content.iter_any(),
                    media_type=content_type,
                    status_code=response.status
                )

            # テキストコンテンツの処理
            content = await response.text()
            
            # HTMLの場合はリンクを修正
            if content_type.startswith('text/html'):
                content = await proxy_server.modify_content(content, "")
            
            return Response(
                content=content,
                media_type=content_type,
                status_code=response.status
            )

    except Exception as e:
        logger.error(f"Error proxying request: {e}")
        return {"error": str(e)}

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    
    print(f"""
    プロキシサーバーを起動しています...
    
    使用方法:
    1. ブラウザで http://localhost:{args.port}/set-target?url=<target-url> にアクセスして対象サイトを設定
    2. http://localhost:{args.port} にアクセスしてプロキシされたサイトを表示
    
    サーバーを停止するには Ctrl+C を押してください。
    """)
    
    uvicorn.run(app, host="0.0.0.0", port=args.port)
