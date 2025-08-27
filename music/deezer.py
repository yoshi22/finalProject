# music/deezer.py  ※全文コピペ
"""
Deezer Public API wrapper
Docs: https://developers.deezer.com/api
"""

from typing import List, Dict, Optional
import requests, logging
from django.conf import settings

DEEZER_ROOT = getattr(settings, "DEEZER_ROOT", "https://api.deezer.com")
_log = logging.getLogger(__name__)


def _get(url: str, params: Optional[Dict] = None) -> Dict:
    try:
        res = requests.get(url, params=params or {}, timeout=10)
        res.raise_for_status()
        return res.json()
    except Exception as exc:
        _log.warning("Deezer API error: %s", exc)
        return {}


# ------------------------------------------------------------
# ✨ 必ずこの名前で公開
def search(query: str, limit: int = 5) -> List[Dict]:
    """
    text クエリでトラック検索し、正規化した dict を返す
    """
    data = _get(f"{DEEZER_ROOT}/search", {"q": query, "limit": limit})
    return [_normalize_track(t) for t in data.get("data", [])]


def get(track_id: str) -> Dict:
    return _normalize_track(_get(f"{DEEZER_ROOT}/track/{track_id}"))


# ------------------------------------------------------------
def _normalize_track(t: Dict) -> Dict:
    if not t:
        return {}
    return {
        "provider": "deezer",
        "id": str(t["id"]),
        "title": t["title"],
        "artist": t["artist"]["name"],
        "album": t["album"]["title"],
        "preview_url": t.get("preview"),  # 30-sec MP3
        "art_url": t["album"].get("cover_xl") or t["album"].get("cover_big"),
        "isrc": t.get("isrc"),
        "duration": t.get("duration"),
        "bpm": t.get("bpm"),  # Deezer は bpm も返す
    }
