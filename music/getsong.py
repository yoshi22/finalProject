import hashlib, logging, urllib.parse, requests
from typing import Dict, Optional
from django.conf import settings
from django.core.cache import cache

LOG       = logging.getLogger(__name__)
API_ROOT  = "https://api.getsong.co"
API_KEY   = getattr(settings, "GETSONGBPM_KEY", "")
LOCK_KEY  = "gsb:lock"
LOCK_SECS = 600          # 10 分

# ---------- low-level GET with global lock ------------------------
def _get(endpoint: str, params: Dict) -> Optional[Dict]:
    if not API_KEY or cache.get(LOCK_KEY):
        return None

    params["api_key"] = API_KEY
    try:
        res = requests.get(API_ROOT + endpoint, params=params, timeout=8)
        if res.status_code == 429:
            cache.set(LOCK_KEY, 1, LOCK_SECS)
            LOG.warning("GetSongBPM 429 – locked for %s s", LOCK_SECS)
            return None
        res.raise_for_status()
        return res.json()
    except requests.exceptions.RequestException as exc:
        LOG.warning("GetSongBPM error: %s", exc)
        return None

# ---------- public helper ----------------------------------------
def audio_features(*, query: str) -> Optional[Dict]:
    """
    曲名+アーティスト → {'key': 'G', 'tempo': 78}
    取れない場合 None。30 日キャッシュ。
    """
    # memcached セーフキー（md5 32 桁に圧縮）
    ck = "gsb:" + hashlib.md5(query.lower().encode()).hexdigest()

    sentinel = cache.get(ck)
    if sentinel is not None:          # '' / dict のどちらでもヒット
        return sentinel or None

    look = urllib.parse.quote_plus(query)
    data = _parse(
        _get("/search/", {"type": "song", "lookup": look, "limit": 1})
    )
    cache.set(ck, data or "", 60 * 60 * 24 * 30)     # 30 日
    return data

# ---------- JSON → dict ------------------------------------------
def _parse(js: Optional[Dict]) -> Optional[Dict]:
    if not js or not js.get("search"):
        return None
    hits = js["search"]
    if isinstance(hits, dict):
        hits = [hits]
    first = hits[0]
    key   = first.get("key_of")
    tempo = first.get("tempo")
    if not key or not tempo:
        return None
    try:
        tempo = int(float(tempo))
    except ValueError:
        return None
    return {"key": key, "tempo": tempo}
