# music/spotify.py
"""
Light-weight Spotify helper
───────────────────────────
・client-credentials flow
・audio_analysis.track.key を中央 (C4≒60) に合わせ、±6 半音を歌唱レンジとみなす
"""
from __future__ import annotations
import os
import time
import logging
from typing import Final, Optional, Tuple

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

CID: Final[str] = os.getenv("SPOTIFY_CLIENT_ID", "")
SECRET: Final[str] = os.getenv("SPOTIFY_CLIENT_SECRET", "")

# 起動時に資格情報がない場合は 1 度だけ警告
if not CID or not SECRET:
    logging.warning("SPOTIFY_CLIENT_ID / SECRET が未設定。pitch_range は常に None を返します。")

_sp: Optional[spotipy.Spotify] = None
_token_exp: float = 0.0


def _client() -> spotipy.Spotify:
    """
    キャッシュ付きで Spotify API クライアントを返す。
    Spotipy ≥2.25 は get_access_token(as_dict=False) がデフォルト。
    """
    global _sp, _token_exp

    if _sp and _token_exp - time.time() > 30:
        return _sp

    auth = SpotifyClientCredentials(client_id=CID, client_secret=SECRET)

    try:
        token_info = auth.get_access_token(as_dict=True)  # ← ★ここが唯一の変更点
        access_token = token_info["access_token"]
        _token_exp = token_info["expires_at"]
    except TypeError:
        # Spotipy が古い場合は string で返るので、フォールバック
        access_token = auth.get_access_token()
        _token_exp = time.time() + 3600  # 1h 有効と仮定

    _sp = spotipy.Spotify(auth=access_token, requests_timeout=5, retries=2)
    return _sp


# ────────────────────────────────────────────────
def spotify_id(artist: str, title: str) -> Optional[str]:
    """Search & return first matching track id (or None)."""
    try:
        res = _client().search(f"track:{title} artist:{artist}", type="track", limit=1)
        items = res["tracks"]["items"]
        return items[0]["id"] if items else None
    except Exception as exc:
        logging.warning("Spotify search error: %s", exc)
        return None


def pitch_range(track_id: str) -> Optional[Tuple[int, int]]:
    """(low_midi, high_midi) or None"""
    try:
        ana = _client().audio_analysis(track_id)
        key = ana["track"]["key"]
        if key == -1:
            return None
        base = 60 + key
        return base - 6, base + 6
    except spotipy.SpotifyException as exc:
        # 401 ⇒ トークン失効 → 再取得
        if exc.http_status == 401:
            _client.cache_token = None          # 强制リフレッシュ
            return pitch_range(track_id)
        # 403 / 404 はすぐ None
        logging.warning("audio_analysis 403/404: %s", exc)
        return None
    except Exception as exc:
        logging.warning("audio_analysis error: %s", exc)
        return None
