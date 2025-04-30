"""
iTunes Search helper
────────────────────
・1 曲 30 秒プレビュー URL を取得
・403 / 5xx を握りつぶし、結果 (None も含む) をキャッシュ
・キャッシュキーは safe_key() で Memcached-safe に変換
"""
from __future__ import annotations

import logging
import random
import time
from typing import Optional

import requests
from django.core.cache import cache

from .cache_utils import safe_key  # ← 必須

ITUNES_API = "https://itunes.apple.com/search"


def itunes_preview(
    term: str,
    *,
    use_cache: bool = True,
    cache_ttl: int = 60 * 60 * 24,
    country: str = "us",
) -> Optional[str]:
    """
    term（例: "Adele Hello"）で iTunes Search API を叩き、
    プレビュー URL (30 秒) を返す。取れなければ None。
    """
    key = safe_key("itunes", term.lower())

    if use_cache and (hit := cache.get(key)) is not None:
        return hit  # None もキャッシュされている可能性あり

    # リクエストが集中すると iTunes は 403 を返すため、
    # 微小な jitter + UA 明示で負荷を散らす
    time.sleep(random.random() * 0.3)

    try:
        resp = requests.get(
            ITUNES_API,
            params=dict(term=term, media="music", limit=1, country=country),
            headers={"User-Agent": "Mozilla/5.0"},
            timeout=4,
        )
        resp.raise_for_status()
        items = resp.json().get("results", [])
        url = items[0].get("previewUrl") if items else None
    except Exception as exc:  # pylint: disable=broad-except
        logging.warning("itunes_preview error: %s", exc)
        url = None

    if use_cache:
        cache.set(key, url, cache_ttl)
    return url
