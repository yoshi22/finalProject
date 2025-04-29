import logging, requests, os
from functools import lru_cache

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

sp = spotipy.Spotify(auth_manager=SpotifyClientCredentials(
        client_id=os.getenv("SPOTIFY_CLIENT_ID"),
        client_secret=os.getenv("SPOTIFY_CLIENT_SECRET")))

@lru_cache(maxsize=4096)
def spotify_id(artist: str, title: str) -> str | None:
    """Return Spotify track ID via Search API."""
    q = f"track:{title} artist:{artist}"
    res = sp.search(q, type="track", limit=1)
    items = res.get("tracks", {}).get("items")
    return items[0]["id"] if items else None

@lru_cache(maxsize=4096)
def pitch_range(sp_id: str) -> tuple[int,int] | None:
    """
    Rough estimate of [min,max] melody pitch (MIDI) using Audio Analysis.
    Takes the 90th percentile of segment pitches above 0.7 confidence.
    """
    try:
        analysis = sp.audio_analysis(sp_id)  # requires “audio-analysis” scope
        pitches = []
        for seg in analysis["segments"]:
            # seg["pitches"] = 12-dim chroma ; convert to absolute MIDI around key
            idx = max(range(12), key=lambda i: seg["pitches"][i])
            conf = seg["pitches"][idx]
            if conf > 0.7:
                key = analysis["track"]["key"]  # 0=C
                midi = 60 + (idx - key)  # naive, octave center at C4
                pitches.append(midi)
        if not pitches:
            return None
        pitches.sort()
        lo = pitches[int(len(pitches)*0.05)]
        hi = pitches[int(len(pitches)*0.95)]
        return lo, hi
    except Exception as exc:
        logging.warning("Spotify analysis failed: %s", exc)
        return None
