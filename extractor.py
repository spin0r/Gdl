import os
import sys
import shutil
import asyncio
import logging
import urllib.parse
import httpx

logger = logging.getLogger(__name__)

TELEGRAPH_ACCESS_TOKEN = None

def guess_media_type(url: str) -> str:
    """Guess media type (image, video, audio, or other) based on URL extension/path."""
    parsed = urllib.parse.urlparse(url)
    clean_path = parsed.path.lower()
    
    # Check video extensions
    video_exts = ('.mp4', '.m4v', '.mkv', '.webm', '.mov', '.avi', '.wmv', '.flv', '.ts', '.m3u8')
    if any(clean_path.endswith(ext) or ext in clean_path for ext in video_exts):
        return 'video'
        
    # Check image extensions
    image_exts = ('.jpg', '.jpeg', '.png', '.webp', '.gif', '.svg', '.bmp', '.ico', '.tiff', '.avif')
    if any(clean_path.endswith(ext) or ext in clean_path for ext in image_exts):
        return 'image'
        
    # Check audio extensions
    audio_exts = ('.mp3', '.ogg', '.wav', '.flac', '.m4a', '.aac', '.opus')
    if any(clean_path.endswith(ext) or ext in clean_path for ext in audio_exts):
        return 'audio'
        
    return 'file'

def extract_filename(url: str) -> str:
    """Extract a friendly filename from the URL."""
    try:
        parsed = urllib.parse.urlparse(url)
        path_parts = [p for p in parsed.path.split('/') if p]
        if path_parts:
            filename = path_parts[-1]
            # Strip query params if any in filename
            if '?' in filename:
                filename = filename.split('?')[0]
            if len(filename) > 0 and len(filename) < 80:
                return filename
    except Exception:
        pass
    return "media_file"

async def extract_gallery_urls(url: str) -> tuple[list[dict], str]:
    """
    Executes 'gallery-dl --get-urls <url>' asynchronously.
    Returns (list_of_media_items, error_message).
    Each media item is a dict: { "url": str, "type": str, "filename": str, "index": int }
    """
    try:
        gallery_dl_bin = shutil.which("gallery-dl")
        if gallery_dl_bin:
            cmd = [gallery_dl_bin, "--get-urls", url]
        else:
            cmd = [sys.executable, "-m", "gallery_dl", "--get-urls", url]

        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await asyncio.wait_for(process.communicate(), timeout=120)

        if process.returncode != 0:
            err_msg = stderr.decode().strip() or "Unknown error running gallery-dl"
            return [], err_msg

        raw_urls = [line.strip() for line in stdout.decode().splitlines() if line.strip()]
        
        # Filter and structure items
        media_items = []
        for idx, u in enumerate(raw_urls, 1):
            media_type = guess_media_type(u)
            filename = extract_filename(u)
            media_items.append({
                "index": idx,
                "url": u,
                "type": media_type,
                "filename": filename
            })

        return media_items, ""
    except asyncio.TimeoutError:
        return [], "Extraction timed out after 120s."
    except Exception as e:
        logger.error(f"Error executing gallery-dl: {e}")
        return [], str(e)


async def get_telegraph_token() -> str:
    """Get or create a Telegraph API access token."""
    global TELEGRAPH_ACCESS_TOKEN
    if TELEGRAPH_ACCESS_TOKEN:
        return TELEGRAPH_ACCESS_TOKEN

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.telegra.ph/createAccount",
            data={
                "short_name": "GalleryDL",
                "author_name": "Gallery-DL Web & Bot",
            },
            timeout=10.0,
        )
        res_json = response.json()
        if res_json.get("ok"):
            TELEGRAPH_ACCESS_TOKEN = res_json["result"]["access_token"]
            return TELEGRAPH_ACCESS_TOKEN
        raise Exception(f"Failed to create Telegraph account: {res_json}")


async def upload_to_telegraph(title: str, extracted_urls: list[str], target_url: str) -> str:
    """Creates a telegra.ph page containing all extracted links."""
    token = await get_telegraph_token()

    link_children = []
    for i, u in enumerate(extracted_urls):
        if i > 0:
            link_children.append({"tag": "br"})
        link_children.append({"tag": "a", "attrs": {"href": u}, "children": [u]})

    nodes = [
        {
            "tag": "p",
            "children": [
                "Source: ",
                {"tag": "a", "attrs": {"href": target_url}, "children": [target_url]},
                {"tag": "br"},
                f"Total Extracted Links: {len(extracted_urls)}",
            ],
        },
        {"tag": "hr"},
        {
            "tag": "p",
            "children": link_children,
        },
    ]

    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.telegra.ph/createPage",
            json={
                "access_token": token,
                "title": title[:256],
                "author_name": "Gallery-DL Web",
                "content": nodes,
                "return_content": False,
            },
            timeout=15.0,
        )
        res_json = response.json()
        if res_json.get("ok"):
            return f"https://telegra.ph/{res_json['result']['path']}"
        else:
            raise Exception(f"Telegraph API error: {res_json.get('error')}")
