# music/musicstax.py  ★フルコード★

"""
MusicStax API wrapper
Docs: https://musicstax.com/api
必要環境変数:
  MUSICSTAX_KEY=<あなたのAPIキー>
"""

from typing import Dict, Optional
import requests, logging
from django.conf import settings

MS_ROOT   = getattr(settings, "MUSICSTAX_ROOT", "https://musicstax.com/api")
API_KEY   = settings.MUSICSTAX_KEY
VERSION   = "v1"
_log = logging.getLogger(__name__)


def _get(endpoint: str, params: Dict) -> Optional[Dict]:
    if not API_KEY:
        _log.error("MUSICSTAX_KEY が未設定です")
        return None

    headers = {"x-api-key": API_KEY}
    try:
        res = requests.get(f"{MS_ROOT}/{VERSION}/{endpoint}",
                           params=params,
                           headers=headers,
                           timeout=10)
        if res.status_code == 404:
            return None
        res.raise_for_status()
        return res.json()
    except Exception as exc:
        _log.warning("MusicStax API error: %s", exc)
        return None


# ------------------------------------------------------------------
# 公開関数  ✨ views から import される名前
# ------------------------------------------------------------------
def audio_features(*,
                   isrc: Optional[str] = None,
                   query: Optional[str] = None) -> Optional[Dict]:
    """
    Audio features を取得して正規化して返す。
    優先順位: ISRC → テキスト検索
    返却例:
      {
        "key": "A",
        "mode": "major",
        "tempo": 120.0,
        "energy": 0.83,
        "danceability": 0.76
      }
    """
    if isrc:
        data = _get("track", {"isrc": isrc})
    elif query:
        res = _get("search", {"q": query, "limit": 1})
        data = (res or {}).get("data", [{}])[0]
    else:
        return None

    if not data:
        return None

    # Not all fields are guaranteed
    return {
        "key": data.get("key"),
        "mode": data.get("mode"),
        "tempo": data.get("tempo") or data.get("bpm"),
        "energy": data.get("energy"),
        "danceability": data.get("danceability"),
    }
