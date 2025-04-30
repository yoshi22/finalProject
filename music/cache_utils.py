# music/cache_utils.py
"""
Utilities for generating cache-safe keys
----------------------------------------

* Memcached は 250 文字制限 & 制御文字 / 半角スペースなど NG
* 「可読スラッグ + MD5 ハッシュ」のハイブリッドで安全化
"""
from __future__ import annotations

import hashlib
import re
from typing import Final

# NG 文字を "_" に置換する正規表現
_INVALID: Final = re.compile(r"[^A-Za-z0-9_.-]")

def safe_key(namespace: str, raw: str, *, max_slug: int = 60) -> str:
    """
    >>> safe_key("itunes", "Beyoncé CRAZY IN LOVE")
    'itunes:Beyonc_CRAZY_IN_LOVE:4d2c596b3a'
    """
    # ① 可読部分（長すぎると意味がないので truncate）
    slug = _INVALID.sub("_", raw)[:max_slug]

    # ② ハッシュで一意性を担保（usedforsecurity=False で FIPS 回避）
    digest = hashlib.md5(raw.encode("utf-8"), usedforsecurity=False).hexdigest()[:10]

    return f"{namespace}:{slug}:{digest}"
