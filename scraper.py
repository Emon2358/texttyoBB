import asyncio
import aiohttp
from bs4 import BeautifulSoup
from fastapi import FastAPI, Request, Response
from fastapi.responses import HTMLResponse, StreamingResponse
import uvicorn
from urllib.parse import urljoin, urlparse
import re
from typing import Optional
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

class ProxyServer:
    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.target_domain = None
        self.scheme = None

    async def ensure_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()

    def set_target(self, url: str):
        parsed = urlparse(url)
        self.target_domain = parsed.netloc
        self.scheme = parsed.scheme

    async def close(self):
        if self.session:
            await self.session.close()
            self.session = None

    def is_same_domain(self, url: str) -> bool:
        try:
            parsed = urlparse(url)
            return parsed.netloc == self.target_domain
        except:
            return False

    async def modify_content(self, content: str, base_path: str) -> str:
        soup = BeautifulSoup(content, 'html.parser')

        # Update all links to go through our proxy
        for tag in soup.find_all(['a', 'link', 'script', 'img', 'form']):
            for attr in ['href', 'src', 'action']:
                if tag.get(attr):
                    url = tag[attr]
                    if url.startswith('//'):
                        url = f"{self.scheme}:{url}"
                    if url.startswith('/'):
                        url = f"{self.scheme}://{self.target_domain}{url}"
                    if self.is_same_domain(url):
                        tag[attr] = f"/{base_path}{urlparse(url).path}"

        # Handle inline styles with url()
        for tag in soup.find_all(style=True):
            style = tag['style']
            urls = re.findall(r'url\([\'"]?(.*?)[\'"]?\)', style)
            for url in urls:
                if url.startswith('/'):
                    new_url = f"/{base_path}{url}"
                    style = style.replace(f"url({url})", f"url({new_url})")
                    tag['style'] = style

        # Handle style tags
        for style in soup.find_all('style'):
            if style.string:
                urls = re.findall(r'url\([\'"]?(.*?)[\'"]?\)', style.string)
                for url in urls:
                    if url.startswith('/'):
                        new_url = f"/{base_path}{url}"
                        style.string = style.string.replace(
                            f"url({url})", f"url({new_url})")

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
    return {"status": "success", "target": url}

@app.get("/{path:path}")
async def proxy(path: str, request: Request):
    if not proxy_server.target_domain:
        return {"error": "Target not set. Please use /set-target?url=... first"}

    # Construct target URL
    target_url = f"{proxy_server.scheme}://{proxy_server.target_domain}/{path}"
    if request.query_params:
        target_url += f"?{request.query_params}"

    logger.info(f"Proxying request to: {target_url}")

    try:
        async with proxy_server.session.get(target_url) as response:
            content_type = response.headers.get('Content-Type', '')
            
            # Handle binary responses (images, etc.)
            if not content_type.startswith('text/') and \
               not content_type.startswith('application/javascript') and \
               not content_type.startswith('application/json'):
                return StreamingResponse(
                    response.content.iter_any(),
                    media_type=content_type
                )

            # Handle text content
            content = await response.text()
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
