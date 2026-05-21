import requests
import logging
import time

logger = logging.getLogger(__name__)

NSE_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/csv,application/csv,*/*",
    "Accept-Language": "en-IN,en;q=0.9",
    "Referer": "https://www.nseindia.com/",
}

_session: requests.Session = None


def get_nse_session() -> requests.Session:
    global _session
    if _session is None:
        _session = requests.Session()
        _session.headers.update(NSE_HEADERS)
    return _session


def fetch_nse_csv(url: str, retries: int = 3) -> bytes:
    """Fetch a CSV from NSE archives, populating cookies first. Returns raw bytes."""
    sess = get_nse_session()
    for attempt in range(retries):
        try:
            # Refresh cookies
            sess.get("https://www.nseindia.com/", timeout=15)
            resp = sess.get(url, timeout=30)
            resp.raise_for_status()
            # Detect HTML login wall
            if b"<!DOCTYPE" in resp.content[:100] or b"<html" in resp.content[:100]:
                logger.warning(f"NSE returned HTML for {url} (attempt {attempt + 1})")
                if attempt < retries - 1:
                    time.sleep(30)
                    continue
                raise ValueError("NSE returned HTML instead of CSV")
            return resp.content
        except Exception as e:
            logger.error(f"NSE fetch failed for {url}: {e} (attempt {attempt + 1})")
            if attempt < retries - 1:
                time.sleep(30)
    raise RuntimeError(f"Failed to fetch {url} after {retries} retries")
