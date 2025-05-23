"""
music/getsong.py  ―  GetSongBPM API helper  (2025-05-23)

* 8 秒タイムアウト／ネットワーク系エラーは **15 分だけ抑止**  
* 429 (Too Many Requests) を受けた場合は **グローバルロック 10 分**  
* 成功レスポンスは 30 日キャッシュ  
"""

from __future__ import annotations

import hashlib
import logging
import urllib.parse
from typing import Dict, Optional

import requests
from django.conf import settings
from django.core.cache import cache

# ------------------------------------------------------------------
LOG = logging.getLogger(__name__)

API_ROOT = "https://api.getsong.co"
API_KEY: str = getattr(settings, "GETSONGBPM_KEY", "")

LOCK_KEY = "gsb:lock"       # True が入っている間は API を叩かない
LOCK_SECS = 600             # 10 分

FAIL_TTL = 60 * 15          # タイムアウト等の再試行間隔（15 分）
HIT_TTL  = 60 * 60 * 24 * 30  # 正常ヒットは 30 日
# ------------------------------------------------------------------


# ---------- low-level GET with global lock ------------------------
def _get(endpoint: str, params: Dict) -> Optional[Dict]:
    if not API_KEY or cache.get(LOCK_KEY):
        return None

    params["api_key"] = API_KEY
    try:
        # ★ タイムアウトを 15 秒に拡大
        res = requests.get(API_ROOT + endpoint, params=params, timeout=15)

        if res.status_code == 429:
            cache.set(LOCK_KEY, 1, LOCK_SECS)
            LOG.warning("GetSongBPM 429 – locked for %s s", LOCK_SECS)
            return None

        res.raise_for_status()
        return res.json()

    except requests.exceptions.RequestException as exc:
        LOG.warning("GetSongBPM error: %s", exc)
        # ★ 10 分だけ“失敗”をキャッシュして同じ曲への連続リトライを防ぐ
        if "lookup" in params:
            ck = "gsb:" + hashlib.md5(params["lookup"].lower().encode()).hexdigest()
            cache.set(ck, "", 600)
        return None



# ---------- public helper ----------------------------------------
def audio_features(*, query: str) -> Optional[Dict]:
    """
    曲名+アーティスト → {'key': 'G', 'tempo': 78}  
    取れない場合は None を返す（失敗は FAIL_TTL＝15 分キャッシュ）
    """
    # memcached セーフキー（md5 32 桁に圧縮）
    ck = "gsb:" + hashlib.md5(query.lower().encode()).hexdigest()

    sentinel = cache.get(ck)      # '' または dict
    if sentinel is not None:
        return sentinel or None   # 空文字なら失敗扱い

    lookup = urllib.parse.quote_plus(query)
    js = _get("/search/", {"type": "song", "lookup": lookup, "limit": 1})
    data = _parse(js)

    # --- キャッシュ戦略 ------------------------------------------
    if data:                                   # 正常ヒット
        cache.set(ck, data, HIT_TTL)
    else:                                      # 失敗
        # 429 ロック中はロックで制御、個別キャッシュは張らない
        ttl = 0 if cache.get(LOCK_KEY) else FAIL_TTL
        if ttl:
            cache.set(ck, "", ttl)
    return data


# ---------- JSON → dict ------------------------------------------
def _parse(js: Optional[Dict]) -> Optional[Dict]:
    """
    API JSON から最初のヒットを抽出  
    key が 'key_of', tempo が文字列で返る仕様に合わせて整形
    """
    if not js or not js.get("search"):
        return None

    hits = js["search"]
    if isinstance(hits, dict):
        hits = [hits]

    first = hits[0]
    key   = (first.get("key_of") or "").strip()
    tempo = first.get("tempo")

    if not key or not tempo:
        return None

    try:
        tempo_int = int(float(tempo))
    except ValueError:
        return None

    return {"key": key, "tempo": tempo_int}
