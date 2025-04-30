# music/itunes.py   ※ファイル全体を確認して修正
import logging
import requests
from typing import Optional
from django.core.cache import cache

from .cache_utils import safe_key          # ← 必ず import する

ITUNES_API = "https://itunes.apple.com/search"

def itunes_preview(term: str,
                   *,
                   use_cache: bool = True,
                   cache_ttl: int = 60 * 60 * 24,
                   country: str = "us") -> Optional[str]:
    """
    term で iTunes Search API をたたき 30 秒試聴 URL を返す
    """
    key = safe_key("itunes", term)        # ← 必ず safe_key を通す

    if use_cache and (cached := cache.get(key)) is not None:
        return cached                     # None もキャッシュに入っているかも

    try:
        resp = requests.get(
            ITUNES_API,
            params=dict(term=term, media="music", limit=1, country=country),
            timeout=5,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        url = results[0].get("previewUrl") if results else None
    except Exception as exc:              # pylint: disable=broad-except
        logging.warning("itunes_preview error: %s", exc)
        url = None

    if use_cache:
        cache.set(key, url, cache_ttl)
    return url
