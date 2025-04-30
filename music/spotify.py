# music/spotify.py
"""
Light-weight Spotify helper
───────────────────────────
・client-credentials flow
・音程キーを中央 C4 (=60) に合わせ ±6 半音を歌唱レンジとみなす
・audio_features → audio_analysis の 2 段 Fallback（403/404 削減）
・Django cache（無い場合はローカル dict）で結果を保存（None も保存）
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Final, Optional, Tuple

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# ──────────────────────────────────────────────────────────
# Spotify 認証情報
# ──────────────────────────────────────────────────────────
CID: Final[str] = os.getenv("SPOTIFY_CLIENT_ID", "")
SECRET: Final[str] = os.getenv("SPOTIFY_CLIENT_SECRET", "")

if not CID or not SECRET:
    logging.warning(
        "SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET が未設定。"
        "spotify_id / pitch_range は常に None を返します。"
    )

# ──────────────────────────────────────────────────────────
# Django cache がなければ簡易ローカルキャッシュにフォールバック
# ──────────────────────────────────────────────────────────
try:
    from django.core.cache import cache as _dj_cache  # type: ignore
except ModuleNotFoundError:  # Django を経由しない CLI など
    _local_cache: Dict[str, Tuple[Optional[Tuple[int, int]], float]] = {}

    class _DummyCache:  # pylint: disable=too-few-public-methods
        def get(self, key: str) -> Any:
            data = _local_cache.get(key)
            if not data:
                return None
            value, exp = data
            if exp < time.time():
                _local_cache.pop(key, None)
                return None
            return value

        def set(self, key: str, val: Any, ttl: int) -> None:
            _local_cache[key] = (val, time.time() + ttl)

    _dj_cache = _DummyCache()  # type: ignore

cache = _dj_cache  # 統一参照名

# ──────────────────────────────────────────────────────────
# Spotipy クライアント（アクセストークンをプロセス内で共有）
# ──────────────────────────────────────────────────────────
_sp: Optional[spotipy.Spotify] = None
_token_exp: float = 0.0  # epoch seconds


def _client() -> spotipy.Spotify:
    """
    キャッシュ付きで Spotipy クライアントを返す。

    Spotipy ≥2.25 では get_access_token(as_dict=False) がデフォルト。
    """
    global _sp, _token_exp  # pylint: disable=global-statement

    # 30 秒以上有効なら使い回す
    if _sp and (_token_exp - time.time()) > 30:
        return _sp

    auth = SpotifyClientCredentials(client_id=CID, client_secret=SECRET)

    try:
        token_info = auth.get_access_token(as_dict=True)  # Spotipy 2.25+
        access_token = token_info["access_token"]
        _token_exp = token_info["expires_at"]
    except TypeError:  # 古い Spotipy
        access_token = auth.get_access_token()
        _token_exp = time.time() + 3600  # 1 時間有効と仮定

    _sp = spotipy.Spotify(auth=access_token, requests_timeout=5, retries=2)
    return _sp


# ──────────────────────────────────────────────────────────
# Public helper: Spotify track を検索し ID を返す
# ──────────────────────────────────────────────────────────
def spotify_id(artist: str, title: str) -> Optional[str]:
    """Search & return first matching track id (or None)."""
    if not CID or not SECRET:
        return None
    try:
        res = _client().search(
            f"track:{title} artist:{artist}", type="track", limit=1
        )
        items = res["tracks"]["items"]
        return items[0]["id"] if items else None
    except Exception as exc:  # pylint: disable=broad-except
        logging.warning("Spotify search error: %s", exc)
        return None


# ──────────────────────────────────────────────────────────
# Public helper: 歌唱可能レンジ (MIDI low, high) を返す
# ──────────────────────────────────────────────────────────
def pitch_range(
    track_id: str,
    *,
    use_cache: bool = False,
    cache_ttl: int = 60 * 60 * 24,  # 1 day
) -> Optional[Tuple[int, int]]:
    """
    Parameters
    ----------
    track_id : str
        Spotify track ID
    use_cache : bool
        True にすると Django cache へ read/write する
    cache_ttl : int
        キャッシュ有効秒数。デフォルト 1 日。

    Returns
    -------
    (low_midi, high_midi) | None
        取得失敗時は None
    """
    if not CID or not SECRET:
        return None

    cache_key = f"pitch_range:{track_id}"

    # ─── キャッシュヒット ───────────────────────────────
    if use_cache:
        cached = cache.get(cache_key)
        if cached is not None:
            return cached  # None も保存している

    client = _client()
    result: Optional[Tuple[int, int]] = None

    # ─── ❶ audio_features（100 件まとめて取れる・403 が少ない） ─────
    try:
        feat = client.audio_features([track_id])[0]
        key = feat and feat["key"]
        if key not in (None, -1):
            base = 60 + key
            result = (base - 6, base + 6)
    except spotipy.SpotifyException as exc:
        logging.info("audio_features %s: %s", exc.http_status, exc)

    # ─── ❷ features 失敗時のみ audio_analysis へ Fallback ────────────
    if result is None:
        try:
            ana = client.audio_analysis(track_id)
            key = ana["track"]["key"]
            if key != -1:
                base = 60 + key
                result = (base - 6, base + 6)
        except spotipy.SpotifyException as exc:
            if exc.http_status == 401:
                # トークン失効 → 強制リフレッシュして 1 回だけ再帰
                global _sp  # pylint: disable=global-statement
                _sp = None
                return pitch_range(
                    track_id, use_cache=use_cache, cache_ttl=cache_ttl
                )
            logging.warning("audio_analysis %s: %s", exc.http_status, exc)
            result = None
        except Exception as exc:  # pylint: disable=broad-except
            logging.warning("audio_analysis error: %s", exc)
            result = None

    # ─── キャッシュ保存（None も保存して無駄リクエスト削減） ────────
    if use_cache:
        cache.set(cache_key, result, cache_ttl)

    return result
