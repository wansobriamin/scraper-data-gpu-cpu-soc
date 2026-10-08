import hashlib
import time
from pathlib import Path
from urllib import robotparser
from urllib.parse import urlparse
from typing import Optional
import requests

CACHE_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"
CACHE_DIR.mkdir(parents=True, exist_ok=True)

DEFAULT_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/128.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


class PoliteFetcher:
    def __init__(
        self,
        delay: float = 2.0,
        timeout: int = 20,
        use_cache: bool = True,
        ignore_robots: bool = False,
    ):
        self.delay = delay
        self.timeout = timeout
        self.use_cache = use_cache
        self.ignore_robots = ignore_robots
        self.session = requests.Session()
        self.session.headers.update(DEFAULT_HEADERS)
        self._robots: dict = {}
        self._last_fetch = 0.0

    def _robots_allowed(self, url: str) -> bool:
        if self.ignore_robots:
            return True
        
        parsed = urlparse(url)
        base = f"{parsed.scheme}://{parsed.netloc}"
        if base not in self._robots:
            rp = robotparser.RobotFileParser()
            rp.set_url(f"{base}/robots.txt")
            try:
                rp.read()
            except Exception:
                pass
            self._robots[base] = rp
        ua = DEFAULT_HEADERS["User-Agent"].split("/")[0]
        return self._robots[base].can_fetch(ua, url)

    def _cache_path(self, url: str) -> Path:
        key = hashlib.sha256(url.encode()).hexdigest()[:16]
        return CACHE_DIR / f"{key}.html"

    def get(self, url: str, force: bool = False) -> Optional[str]:
        path = self._cache_path(url)
        if self.use_cache and path.exists() and not force:
            print(f"[CACHE] {url}")
            return path.read_text(encoding="utf-8", errors="replace")

        if not self._robots_allowed(url):
            print(f"[DITOLAK robots.txt] {url}")
            return None

        elapsed = time.time() - self._last_fetch
        if elapsed < self.delay:
            time.sleep(self.delay - elapsed)

        try:
            resp = self.session.get(url, timeout=self.timeout)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[HTTP ERROR] {url}: {e}")
            return None
        finally:
            self._last_fetch = time.time()

        html = resp.text
        path.write_text(html, encoding="utf-8")
        print(f"[FETCH ] {url}")
        return html