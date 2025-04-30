from .spotify import cache
import logging
import requests

def itunes_preview(term: str, ttl: int = 60 * 60 * 24) -> str | None:
    key = f"itunes:{term}"
    cached = cache.get(key)
    if cached is not None:
        return cached

    try:
        res = requests.get(
            "https://itunes.apple.com/search",
            params={"term": term, "limit": 1, "media": "music"},
            timeout=2,          # ★ ここを 10 → 2 秒に短縮
        )
        url = res.json()["results"][0]["previewUrl"]
    except Exception:           # noqa: BLE001
        url = None
    cache.set(key, url, ttl)
    return url
