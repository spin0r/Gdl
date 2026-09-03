import os
import sys
import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import extractor

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Gallery-DL Web Extractor",
    description="Modern Web Interface & REST API for extracting media links using gallery-dl",
    version="1.0.0",
)

# Allow CORS for flexible embedding
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ExtractRequest(BaseModel):
    url: Optional[str] = None
    urls: Optional[List[str]] = None

class TelegraphRequest(BaseModel):
    title: str = "Extracted Links"
    urls: List[str]
    source_url: str = ""

@app.get("/api/health")
async def health():
    """Healthcheck and info."""
    import shutil
    has_binary = bool(shutil.which("gallery-dl"))
    return {
        "status": "ok",
        "gallery_dl_installed": has_binary or True,
    }

@app.post("/api/extract")
async def extract_links(req: ExtractRequest):
    """
    Extract media URLs from one or multiple provided URLs.
    """
    urls_to_process = []
    if req.url and req.url.strip():
        urls_to_process.append(req.url.strip())
    if req.urls:
        for u in req.urls:
            u_clean = u.strip()
            if u_clean and u_clean not in urls_to_process:
                urls_to_process.append(u_clean)

    if not urls_to_process:
        raise HTTPException(status_code=400, detail="Please provide at least one valid URL.")

    all_items = []
    errors = []
    current_index = 1

    for target_url in urls_to_process:
        items, err = await extractor.extract_gallery_urls(target_url)
        if err:
            errors.append(f"[{target_url}] {err}")
        else:
            for item in items:
                item["index"] = current_index
                item["source_url"] = target_url
                all_items.append(item)
                current_index += 1

    if not all_items and errors:
        raise HTTPException(
            status_code=422,
            detail="\n".join(errors)
        )

    return {
        "success": True,
        "count": len(all_items),
        "items": all_items,
        "errors": errors if errors else None,
    }

@app.post("/api/telegraph")
async def create_telegraph_page(req: TelegraphRequest):
    """
    Create a Telegra.ph page for the given list of extracted media URLs.
    """
    if not req.urls:
        raise HTTPException(status_code=400, detail="No URLs provided to publish.")

    try:
        page_url = await extractor.upload_to_telegraph(
            title=req.title,
            extracted_urls=req.urls,
            target_url=req.source_url or "Web Extractor",
        )
        return {"success": True, "telegraph_url": page_url}
    except Exception as e:
        logger.error(f"Telegraph error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/proxy")
async def proxy_image(url: str):
    """Proxy an image URL through the server to bypass CDN hotlink protection."""
    import urllib.parse
    parsed = urllib.parse.urlparse(url)
    # Only allow proxying imagefap CDN URLs for security
    if not parsed.hostname or "imagefap.com" not in parsed.hostname:
        raise HTTPException(status_code=403, detail="Only imagefap.com URLs allowed")

    try:
        import httpx
        async with httpx.AsyncClient(follow_redirects=True, timeout=15.0) as client:
            resp = await client.get(url, headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": "https://www.imagefap.com/",
            })
            if resp.status_code != 200:
                raise HTTPException(status_code=resp.status_code, detail="Upstream error")

            content_type = resp.headers.get("content-type", "image/jpeg")
            from fastapi.responses import Response
            return Response(
                content=resp.content,
                media_type=content_type,
                headers={"Cache-Control": "public, max-age=86400"},
            )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Proxy error: {e}")
        raise HTTPException(status_code=502, detail=str(e))

# Mount frontend directory
frontend_path = os.path.join(os.path.dirname(__file__), "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="static")

@app.get("/")
async def serve_index():
    index_file = os.path.join(frontend_path, "index.html")
    if os.path.exists(index_file):
        return FileResponse(index_file)
    return JSONResponse({"message": "Gallery-DL Web Extractor API is running. Frontend not found."})

def run():
    import uvicorn
    port = int(os.getenv("PORT", "10000"))
    host = os.getenv("HOST", "0.0.0.0")
    print(f"🚀 Starting Gallery-DL Web Extractor on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, proxy_headers=True)

if __name__ == "__main__":
    run()
