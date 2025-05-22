"""
GetSongBPM 無料 Web API ラッパー
Docs: https://getsongbpm.com/api                :contentReference[oaicite:0]{index=0}
API Key は .env または Render の環境変数に GETSONGBPM_KEY として設定。
"""

from typing import Dict, Optional
import logging, requests, urllib.parse
from django.conf import settings

LOG = logging.getLogger(__name__)
API_ROOT = "https://api.getsong.co"
API_KEY  = settings.GETSONGBPM_KEY


def _get(endpoint: str, params: Dict) -> Optional[Dict]:
    if not API_KEY:
        LOG.error("GETSONGBPM_KEY 未設定")
        return None
    hdr = {"x-api-key": API_KEY}
    try:
        res = requests.get(f"{API_ROOT}{endpoint}", params=params, headers=hdr, timeout=8)
        res.raise_for_status()
        return res.json()
    except Exception as exc:
        LOG.warning("GetSongBPM API error: %s", exc)
        return None


def audio_features(*, query: str) -> Optional[Dict]:
    """
    楽曲名+アーティスト名（例: 'queen bohemian rhapsody'）を渡すと
    {"key": "Bb", "mode": "major", "tempo": 144} の dict を返す。
    失敗時は None。
    """
    look = urllib.parse.quote_plus(query)
    js = _get("/search/", {"type": "song", "lookup": look, "limit": 1})
    if not js:
        return None
    songs = js.get("search") or []
    if not songs:
        return None
    s = songs[0]
    return {
        "key": s.get("key_of"),
        "mode": "major" if (s.get("open_key", "") or "A").isupper() else "minor",
        "tempo": s.get("tempo"),
        "danceability": s.get("danceability"),
        "energy": s.get("acousticness"),  # 近似
    }
