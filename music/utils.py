"""
Utility helpers
────────────────
* YouTube Data API v3 を使って検索し、最初の videoId を返す `youtube_id()`
  - API キーが無い／エラーの場合は **None** を返し、呼び出し側で
    `/results` 検索リンクにフォールバックできるようにしてある。
* 同一クエリは Django-cache（memcached / Redis 等）に 12 時間キャッシュ。
"""

from __future__ import annotations

import logging
import os
import re
import requests
from django.conf import settings
from django.core.cache import cache

# ──────────────────────────────────────────────────────────────
#  YouTube Data API  設定
# ──────────────────────────────────────────────────────────────
#   1) Render の Environment 変数 YOUTUBE_API_KEY
#   2) settings.YOUTUBE_API_KEY
#   の順に探索
# ----------------------------------------------------------------
YOUTUBE_API_KEY: str = (
    os.getenv("YOUTUBE_API_KEY") or getattr(settings, "YOUTUBE_API_KEY", "")
)

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"
YOUTUBE_MUSIC_CATEGORY = "10"  # Music
CACHE_TTL = 60 * 60 * 12       # 12 h

_safe_re = re.compile(r"[^a-z0-9]+")


def _cache_key(term: str) -> str:
    """memcached safe key for YouTube id look-ups"""
    return "ytid:" + _safe_re.sub("_", term.lower())


# ──────────────────────────────────────────────────────────────
#  Public helper
# ──────────────────────────────────────────────────────────────
def youtube_id(query: str) -> str | None:
    """
    Return first matching YouTube *videoId* for the given *query*.

    • API キーが無い、あるいは Google が 4xx/5xx を返した場合は **None**。
      呼び出し側では `/results?q=…` などの fallback URL を組み立てて下さい。

    • 成功／失敗にかかわらず結果を Django-cache に入れる（API クォータ節約）。
    """
    if not YOUTUBE_API_KEY:
        logging.info("YOUTUBE_API_KEY not set – youtube_id() will skip API call.")
        return None

    key = _cache_key(query)
    cached = cache.get(key)
    if cached is not None:          # 失敗結果(None) もキャッシュしている
        return cached

    try:
        resp = requests.get(
            YOUTUBE_SEARCH_URL,
            params={
                "key": YOUTUBE_API_KEY,
                "part": "snippet",
                "type": "video",
                "videoCategoryId": YOUTUBE_MUSIC_CATEGORY,
                "maxResults": 1,
                "q": query,
            },
            timeout=5,
        )
        if resp.status_code == 403:
            return None
        resp.raise_for_status()

        items = resp.json().get("items")
        vid: str | None = items[0]["id"]["videoId"] if items else None
        cache.set(key, vid, CACHE_TTL)
        return vid

    except requests.exceptions.HTTPError as exc:
        # 403（quota / key invalid など）を含む HTTPError は握りつぶして None
        status = exc.response.status_code
        logging.warning("YouTube API HTTPError %s – query='%s'", status, query)

    except Exception as exc:
        logging.warning("YouTube search failed for '%s': %s", query, exc)

    # 失敗結果もキャッシュしてスパム的な再試行を避ける
    cache.set(key, None, CACHE_TTL)
    return None
