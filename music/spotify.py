"""
spotify.py
~~~~~~~~~~
Spotipy を薄くラップし、(artist, title) から
・Spotify のトラック ID を取得する `spotify_id`
・そのトラックの推定音域 (lowest_midi, highest_midi) を返す `pitch_range`
―― という２関数だけを公開する小さなヘルパー。

本番では Web API で “audio_analysis” を呼ぶが、
クレデンシャル未設定でもサイトが落ちないよう
両関数とも None を返すフォールバックを備えている。
"""

from __future__ import annotations

import logging
from typing import Optional, Tuple

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
from django.conf import settings


# ------------------------------------------------------------
# Spotipy クライアント (クレデンシャルが無ければ None)
# ------------------------------------------------------------
def _build_client() -> Optional[spotipy.Spotify]:
    cid = getattr(settings, "SPOTIFY_CLIENT_ID", None)
    secret = getattr(settings, "SPOTIFY_CLIENT_SECRET", None)
    if not (cid and secret):
        logging.warning("SPOTIFY_CLIENT_ID / SECRET が未設定。pitch_range は常に None を返します。")
        return None
    auth = SpotifyClientCredentials(client_id=cid, client_secret=secret)
    return spotipy.Spotify(client_credentials_manager=auth, requests_timeout=5, retries=2)


_sp = _build_client()


# ------------------------------------------------------------
# Public helpers
# ------------------------------------------------------------
def spotify_id(artist: str, title: str) -> Optional[str]:
    """
    “Queen” / “Bohemian Rhapsody” などから最も一致率が高い
    Spotify track の ID を返す（見つからなければ None）。
    """
    if _sp is None:
        return None

    q = f"track:{title} artist:{artist}"
    try:
        items = _sp.search(q, type="track", limit=1)["tracks"]["items"]
        return items[0]["id"] if items else None
    except Exception as exc:  # noqa: BLE001
        logging.warning("Spotify search error: %s", exc)
        return None


def pitch_range(track_id: str) -> Optional[Tuple[int, int]]:
    """
    Spotify audio analysis API の中にある
    `segments` → `pitches` を走査して、
      - 最低ピッチ（MIDI note number）
      - 最高ピッチ（MIDI note number）
    のタプルを返す。失敗時は None。
    """
    if _sp is None:
        return None

    try:
        analysis = _sp.audio_analysis(track_id)
        pitches = [max(seg["pitches"]) for seg in analysis["segments"]]
        if not pitches:
            return None
        # `pitches` は 12bin の相対強度。index(1.0) が実音
        # ここでは “一番強い音高” の MIDI ノート番号を大まかに推定
        midi_base = analysis["track"]["key"]  # 0=C, 1=C#/Db, ...
        low = midi_base + min(i * 1 for i, v in enumerate(pitches) if v > 0.5)
        high = midi_base + max(i * 1 for i, v in enumerate(pitches) if v > 0.5)
        return low, high
    except Exception as exc:  # noqa: BLE001
        logging.warning("Spotify audio_analysis error: %s", exc)
        return None
