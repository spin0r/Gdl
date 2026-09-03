#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Standalone ImageFap Extractor
Extracts direct image URLs and metadata from imagefap.com without requiring gallery-dl.

Supports:
- Galleries: https://www.imagefap.com/gallery/12345 or /pictures/12345
- Single Photos: https://www.imagefap.com/photo/12345
- Folders/Organizers: https://www.imagefap.com/organizer/12345
- User Profiles: https://www.imagefap.com/profile/USER
"""

import os
import re
import sys
import json
import time
import html
import random
import urllib.request
import urllib.parse
import urllib.error
import http.cookiejar
from typing import Iterator, Dict, Any, List, Optional, Tuple, Union

BASE_PATTERN = r"(?:https?://)?(?:www\.|beta\.)?imagefap\.com"

RE_GALLERY = re.compile(BASE_PATTERN + r"/(?:gallery\.php\?gid=|gallery/|pictures/)(\d+)", re.IGNORECASE)
RE_IMAGE = re.compile(BASE_PATTERN + r"/photo/(\d+)", re.IGNORECASE)
RE_FOLDER = re.compile(
    BASE_PATTERN + r"/(?:organizer/|(?:usergallery\.php\?user(id)?=([^&#]+)&|profile/([^/?#]+)/galleries\?)folderid=(?!0\b))(\d+|-1)",
    re.IGNORECASE
)
RE_USER = re.compile(
    BASE_PATTERN + r"/(?:profile(?:\.php\?user=|/)([^/?#]+)(?:/galleries(?:\?folderid=0)?)?|usergallery\.php\?userid=(\d+))(?:$|#)",
    re.IGNORECASE
)


class TextHelper:
    """String extraction helper utilities matching gallery-dl parsing behavior."""

    @staticmethod
    def extr(source: str, start: str, end: str) -> Optional[str]:
        """Extract substring between start and end delimiters."""
        if not source:
            return None
        s_idx = source.find(start)
        if s_idx == -1:
            return None
        s_idx += len(start)
        e_idx = source.find(end, s_idx)
        if e_idx == -1:
            return None
        return source[s_idx:e_idx]

    @staticmethod
    def extract(source: str, start: str, end: str, pos: int = 0) -> Tuple[Optional[str], int]:
        """Extract substring between start and end starting from pos, returning (match, new_pos)."""
        s_idx = source.find(start, pos)
        if s_idx == -1:
            return None, pos
        s_idx += len(start)
        e_idx = source.find(end, s_idx)
        if e_idx == -1:
            return None, s_idx
        return source[s_idx:e_idx], e_idx + len(end)

    @classmethod
    def extract_from(cls, source: str):
        """Creates a stateful sequential extractor function."""
        pos = [0]

        def _extr(start: str, end: str) -> Optional[str]:
            match, next_pos = cls.extract(source, start, end, pos[0])
            if match is not None:
                pos[0] = next_pos
            return match

        return _extr

    @staticmethod
    def extract_iter(source: str, start: str, end: str) -> Iterator[str]:
        """Iterate over all substrings bounded by start and end delimiters."""
        pos = 0
        while True:
            s_idx = source.find(start, pos)
            if s_idx == -1:
                break
            s_idx += len(start)
            e_idx = source.find(end, s_idx)
            if e_idx == -1:
                break
            yield source[s_idx:e_idx]
            pos = e_idx + len(end)

    @staticmethod
    def parse_int(val: Any) -> Optional[int]:
        """Safely parse integer from string or return None."""
        if not val:
            return None
        try:
            return int(re.sub(r"[^\d-]", "", str(val)))
        except (ValueError, TypeError):
            return None

    @staticmethod
    def unescape(val: Optional[str]) -> Optional[str]:
        """Unescape HTML entities."""
        return html.unescape(val.strip()) if val else None

    @staticmethod
    def split_html(val: Optional[str]) -> List[str]:
        """Split HTML elements and strip tags."""
        if not val:
            return []
        parts = re.split(r"<[^>]+>", val)
        return [p.strip() for p in parts if p.strip()]

    @staticmethod
    def nameext_from_url(url: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Extract filename and extension from URL."""
        data = data or {}
        parsed = urllib.parse.urlparse(url)
        path = parsed.path
        filename = os.path.basename(path)
        name, ext = os.path.splitext(filename)
        data.update({
            "url": url,
            "filename": name,
            "extension": ext.lstrip(".").lower() if ext else "",
        })
        return data

    @staticmethod
    def make_thumbnail_url(full_url: str) -> Optional[str]:
        """Convert an ImageFap full-size CDN URL to its thumbnail equivalent.
        e.g. .../images/full/AA/BB/ID.jpg -> .../images/thumb/AA/BB/ID.jpg
        """
        if not full_url:
            return None
        if "/images/full/" in full_url:
            return full_url.replace("/images/full/", "/images/thumb/")
        return None


class ImageFapExtractor:
    """Standalone ImageFap Extractor class."""

    ROOT = "https://www.imagefap.com"
    DEFAULT_USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )

    def __init__(self, delay_range: Tuple[float, float] = (0.5, 1.5), user_agent: Optional[str] = None):
        self.delay_range = delay_range
        self.user_agent = user_agent or self.DEFAULT_USER_AGENT
        
        # Setup cookiejar and opener
        self.cookie_jar = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(
            urllib.request.HTTPCookieProcessor(self.cookie_jar)
        )

    def _sleep(self):
        """Throttle requests to avoid rate limits."""
        if self.delay_range and self.delay_range[1] > 0:
            time.sleep(random.uniform(*self.delay_range))

    def request(
        self,
        url: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        data: Optional[Dict[str, Any]] = None
    ) -> str:
        """Make an HTTP request and return the response text."""
        self._sleep()

        if params:
            query = urllib.parse.urlencode(params)
            url = f"{url}?{query}" if "?" not in url else f"{url}&{query}"

        req_headers = {
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
        }
        if headers:
            req_headers.update(headers)

        encoded_data = None
        if data is not None:
            encoded_data = urllib.parse.urlencode(data).encode("utf-8")

        req = urllib.request.Request(url, data=encoded_data, headers=req_headers)

        try:
            with self.opener.open(req, timeout=30) as resp:
                final_url = resp.geturl()
                if "/human-verification" in final_url:
                    content = resp.read().decode("utf-8", errors="replace")
                    msg = TextHelper.extr(content, '<div class="mt-4', '<')
                    if msg:
                        msg = " ".join(msg.partition(">")[2].split())
                    raise RuntimeError(f"ImageFap Human Verification Required: {msg or 'Anti-bot triggered'}")
                
                content = resp.read().decode("utf-8", errors="replace")
                return content
        except urllib.error.HTTPError as e:
            if e.code == 302 and "/human-verification" in e.headers.get("Location", ""):
                raise RuntimeError("ImageFap Human Verification redirect encountered.")
            raise RuntimeError(f"HTTP Error {e.code}: {e.reason}") from e
        except Exception as e:
            raise RuntimeError(f"Request failed for '{url}': {e}") from e

    def extract_single_image(self, photo_id_or_url: str) -> Dict[str, Any]:
        """Extract a single photo info and original direct image URL."""
        m = RE_IMAGE.search(photo_id_or_url)
        photo_id = m.group(1) if m else str(photo_id_or_url).strip("/")

        url = f"{self.ROOT}/photo/{photo_id}/"
        page = self.request(url)

        img_url, pos = TextHelper.extract(page, 'original="', '"')
        if not img_url:
            # Fallback check for alternative image link tag
            img_url, pos = TextHelper.extract(page, '<input id="image_url" value="', '"')

        image_id, pos = TextHelper.extract(page, 'id="imageid_input" value="', '"', pos)
        gallery_id, pos = TextHelper.extract(page, 'id="galleryid_input" value="', '"', pos)

        # Extract json-ld metadata if present
        json_ld_raw = TextHelper.extr(page, '<script type="application/ld+json">', '</script>')
        info = {}
        if json_ld_raw:
            try:
                info = json.loads(json_ld_raw)
            except Exception:
                pass

        title = TextHelper.unescape(info.get("name") or TextHelper.extr(page, "<title>", "</title>"))
        author = info.get("author") or TextHelper.extr(page, 'uploader: "', '"')

        res = TextHelper.nameext_from_url(img_url or "", {
            "title": title,
            "uploader": author,
            "date": info.get("datePublished"),
            "width": TextHelper.parse_int(info.get("width")),
            "height": TextHelper.parse_int(info.get("height")),
            "gallery_id": TextHelper.parse_int(gallery_id),
            "image_id": TextHelper.parse_int(image_id or photo_id),
        })
        return res

    def extract_gallery(self, gallery_id_or_url: str) -> Dict[str, Any]:
        """
        Extract full gallery metadata and all direct image URLs.
        Returns a dict containing gallery details and a list of image items.
        """
        m = RE_GALLERY.search(gallery_id_or_url)
        gid = m.group(1) if m else str(gallery_id_or_url).strip("/")

        url = f"{self.ROOT}/gallery/{gid}"
        page = self.request(url)

        extr = TextHelper.extract_from(page)
        gallery_data = {
            "gallery_id": TextHelper.parse_int(gid),
            "uploader": extr("porn picture gallery by ", " to see hottest"),
            "title": TextHelper.unescape(extr("<title>", "<")),
            "description": TextHelper.unescape((extr('id="gdesc_text"', '<') or "").partition(">")[2]),
            "categories": TextHelper.split_html(extr('id="cnt_cats"', '</div>'))[1::2],
            "tags": TextHelper.split_html(extr('id="cnt_tags"', '</div>'))[1::2],
            "count": TextHelper.parse_int(extr(" 1 of ", ' pics"')),
        }

        image_id = extr('id="img_ed_', '"')
        if not image_id:
            # Try alternate extraction for first image id
            image_id = TextHelper.extr(page, '/photo/', '/')

        total_count = gallery_data["count"] or 0
        images: List[Dict[str, Any]] = []

        # Harvest genuine thumbnail URLs from the gallery HTML page
        gallery_thumbs: Dict[int, str] = {}
        for thumb_m in re.finditer(r'<img\s+[^>]*?src=["\']([^"\']+/images/thumb/[^"\']*?(\d+)\.[a-zA-Z0-9]+(?:\?[^"\']*)?)["\']', page, re.IGNORECASE):
            t_src = thumb_m.group(1)
            pid = TextHelper.parse_int(thumb_m.group(2))
            if pid:
                gallery_thumbs[pid] = t_src

        if image_id:
            ajax_url = f"{self.ROOT}/photo/{image_id}/"
            params = {"gid": gid, "idx": 0, "partial": "true"}
            headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{ajax_url}?pgid=&gid={image_id}&page=0"
            }

            num = 0
            while True:
                ajax_page = self.request(ajax_url, params=params, headers=headers)
                cnt = 0

                # Extract paired (full_url, thumb_url) items from HTML
                pairs = []

                # Strategy 1: <a href="FULL"><img ... src="THUMB"></a>
                for a_match in re.finditer(r'<a\s+[^>]*?href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', ajax_page, re.DOTALL | re.IGNORECASE):
                    href = a_match.group(1)
                    inner = a_match.group(2)
                    if "imagefap" in href or "/images/" in href or "photo" in href:
                        img_m = re.search(r'<img\s+[^>]*?(?:src|data-src)=["\']([^"\']+)["\']', inner, re.IGNORECASE)
                        thumb = img_m.group(1) if img_m else None
                        pairs.append((href, thumb))

                # Strategy 2: Table cells <td>...<a href="FULL">...<img src="THUMB">...</td>
                if not pairs:
                    for td_match in re.finditer(r'<td[^>]*>(.*?)</td>', ajax_page, re.DOTALL | re.IGNORECASE):
                        content = td_match.group(1)
                        a_m = re.search(r'<a\s+[^>]*?href=["\']([^"\']+)["\']', content, re.IGNORECASE)
                        img_m = re.search(r'<img\s+[^>]*?(?:src|data-src)=["\']([^"\']+)["\']', content, re.IGNORECASE)
                        if a_m and ("imagefap" in a_m.group(1) or "/images/" in a_m.group(1)):
                            pairs.append((a_m.group(1), img_m.group(1) if img_m else None))

                # Strategy 3: Standard iteration fallback
                if not pairs:
                    full_urls = list(TextHelper.extract_iter(ajax_page, '<a href="', '"'))
                    all_thumbs = re.findall(r'<img\s+[^>]*?(?:src|data-src)=["\']([^"\']+)["\']', ajax_page, re.IGNORECASE)
                    valid_thumbs = [t for t in all_thumbs if "thumb" in t or "imagefap" in t]
                    for i, u in enumerate(full_urls):
                        thumb = valid_thumbs[i] if i < len(valid_thumbs) else None
                        pairs.append((u, thumb))

                for img_url, thumb_url in pairs:
                    num += 1
                    cnt += 1
                    item = TextHelper.nameext_from_url(img_url)
                    item["num"] = num
                    item["image_id"] = TextHelper.parse_int(item.get("filename"))
                    item["thumbnail_url"] = thumb_url or gallery_thumbs.get(item["image_id"]) or ""
                    images.append(item)

                if not cnt or (cnt < 24 and total_count and num >= total_count):
                    break
                params["idx"] += cnt

        gallery_data["images"] = images
        gallery_data["image_urls"] = [img["url"] for img in images if img.get("url")]
        return gallery_data

    def extract_folder(self, folder_url: str) -> List[Dict[str, Any]]:
        """Extract all gallery IDs and titles from a folder."""
        m = RE_FOLDER.search(folder_url)
        if not m:
            raise ValueError(f"Invalid folder URL: {folder_url}")

        _id, user, profile, folder_id = m.groups()

        if folder_id == "-1":
            folder_name = "Uncategorized"
            if _id:
                url = f"{self.ROOT}/usergallery.php"
                params = {"userid": user, "folderid": "-1", "page": 0}
            else:
                url = f"{self.ROOT}/profile/{user or profile}/galleries"
                params = {"folderid": "-1", "page": 0}
        else:
            folder_name = None
            url = f"{self.ROOT}/organizer/{folder_id}/"
            params = {"page": 0}

        results = []
        while True:
            page = self.request(url, params=params)
            extr = TextHelper.extract_from(page)
            if folder_name is None:
                folder_name = extr("class='blk_galleries'><b>", "</b>") or "Folder"

            cnt = 0
            while True:
                gid = extr(' id="gid-', '"')
                if not gid:
                    break
                title = extr("<b>", "<")
                results.append({
                    "gallery_id": gid,
                    "title": TextHelper.unescape(title),
                    "folder": TextHelper.unescape(folder_name),
                    "url": f"{self.ROOT}/gallery/{gid}"
                })
                cnt += 1

            if cnt < 20:
                break
            params["page"] += 1

        return results

    def extract_user(self, user_url: str) -> List[str]:
        """Extract all folder URLs for a user profile."""
        m = RE_USER.search(user_url)
        if not m:
            raise ValueError(f"Invalid user profile URL: {user_url}")

        user, user_id = m.groups()
        if user:
            url = f"{self.ROOT}/profile/{user}/galleries"
        else:
            url = f"{self.ROOT}/usergallery.php?userid={user_id}"

        params = {"page": 0}
        pnum = 0
        resolved_user = None
        folder_urls = []

        while True:
            page = self.request(url, params=params)
            if resolved_user is None:
                resolved_user = user or user_id

            folders_str = TextHelper.extr(page, ' id="tgl_all" value="', '"')
            if not folders_str:
                break
            folders = folders_str.rstrip("|").split("|")
            if folders[-1] == "-1":
                last = folders.pop()
                if not pnum:
                    folders.insert(0, last)
            elif not folders[0]:
                break

            for fid in folders:
                if fid == "-1":
                    folder_urls.append(f"{self.ROOT}/profile/{resolved_user}/galleries?folderid=-1")
                else:
                    folder_urls.append(f"{self.ROOT}/organizer/{fid}/")

            params["page"] = pnum = pnum + 1
            if f'href="?page={pnum}">{pnum+1}</a>' not in page:
                break

        return folder_urls

    def extract(self, url: str) -> Dict[str, Any]:
        """
        Auto-detect URL type and extract data.
        Returns a dict with 'type' and corresponding extracted content.
        """
        if RE_GALLERY.search(url):
            data = self.extract_gallery(url)
            return {"type": "gallery", "data": data, "urls": data.get("image_urls", [])}

        if RE_IMAGE.search(url):
            data = self.extract_single_image(url)
            return {"type": "image", "data": data, "urls": [data["url"]] if data.get("url") else []}

        if RE_FOLDER.search(url):
            galleries = self.extract_folder(url)
            return {"type": "folder", "galleries": galleries}

        if RE_USER.search(url):
            folders = self.extract_user(url)
            return {"type": "user", "folders": folders}

        raise ValueError(f"URL is not a recognized ImageFap link: {url}")

    def extract_urls(self, url: str) -> List[str]:
        """Convenience function: returns a flat list of direct image URLs from gallery or image URL."""
        res = self.extract(url)
        if res["type"] in ("gallery", "image"):
            return res.get("urls", [])
        elif res["type"] == "folder":
            urls = []
            for g in res.get("galleries", []):
                g_data = self.extract_gallery(g["gallery_id"])
                urls.extend(g_data.get("image_urls", []))
            return urls
        elif res["type"] == "user":
            urls = []
            for folder_url in res.get("folders", []):
                for g in self.extract_folder(folder_url):
                    g_data = self.extract_gallery(g["gallery_id"])
                    urls.extend(g_data.get("image_urls", []))
            return urls
        return []


def main():
    """CLI usage: python imagefap.py <URL> [--json] [--urls-only]"""
    if len(sys.argv) < 2:
        print("Usage: python imagefap.py <IMAGEFAP_URL> [--json | --urls-only]")
        print("Example: python imagefap.py https://www.imagefap.com/gallery/123456")
        sys.exit(1)

    url = sys.argv[1]
    extractor = ImageFapExtractor()

    try:
        if "--urls-only" in sys.argv:
            urls = extractor.extract_urls(url)
            for u in urls:
                print(u)
        elif "--json" in sys.argv:
            data = extractor.extract(url)
            print(json.dumps(data, indent=2))
        else:
            result = extractor.extract(url)
            res_type = result.get("type")
            if res_type == "gallery":
                g = result["data"]
                print(f"📁 Gallery: {g.get('title')} (ID: {g.get('gallery_id')})")
                print(f"👤 Uploader: {g.get('uploader')}")
                print(f"🖼️ Images: {len(g.get('images', []))} / {g.get('count')}")
                print("\nDirect URLs:")
                for img in g.get("images", []):
                    print(f"  [{img.get('num')}] {img.get('url')}")
            elif res_type == "image":
                img = result["data"]
                print(f"🖼️ Title: {img.get('title')}")
                print(f"👤 Uploader: {img.get('uploader')}")
                print(f"🔗 Direct URL: {img.get('url')}")
            elif res_type in ("folder", "user"):
                print(json.dumps(result, indent=2))
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
