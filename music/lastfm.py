# music/lastfm.py
"""
Minimal Last.fm REST API wrapper.

Usage:
    from .lastfm import top_tracks
    tracks = top_tracks(limit=200)
"""
import logging
import requests
from typing import Optional
from django.conf import settings

API_ROOT = "https://ws.audioscrobbler.com/2.0/"
API_KEY = settings.LASTFM_API_KEY
HEADERS = {"User-Agent": settings.LASTFM_USER_AGENT}


def _call(method: str, **params) -> Optional[dict]:
    """Low-level GET → JSON or None on error."""
    params |= {"method": method, "api_key": API_KEY, "format": "json"}
    try:
        r = requests.get(API_ROOT, params=params, headers=HEADERS, timeout=5)
        r.raise_for_status()
        return r.json()
    except Exception as exc:
        logging.warning("Last.fm API error (%s): %s", method, exc)
        return None


# ---------- public helpers ---------- #

def top_tracks(limit: int = 100) -> list[dict]:
    """
    Return world top tracks as list[dict]:
        {"artist": "Coldplay", "title": "Yellow",
         "playcount": 123456, "listeners": 45678, "mbid": "…" }
    """
    data = _call("chart.getTopTracks", limit=limit) or {}
    raw = data.get("tracks", {}).get("track", [])
    if isinstance(raw, dict):  # API returns dict when limit=1
        raw = [raw]

    result = []
    for t in raw:
        result.append(
            {
                "artist": t.get("artist", {}).get("name"),
                "title": t.get("name"),
                "playcount": int(t.get("playcount", 0)),
                "listeners": int(t.get("listeners", 0)),
                "mbid": t.get("mbid") or None,
            }
        )
    return result
