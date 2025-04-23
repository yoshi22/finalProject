import logging
import requests

from django.conf import settings
from django.shortcuts import render, redirect


API_KEY = settings.LASTFM_API_KEY
API_ROOT = settings.LASTFM_ROOT
HEADERS = {"User-Agent": settings.LASTFM_USER_AGENT}


def call_lastfm(params: dict) -> dict | None:
    """Generic Last.fm GET wrapper with basic error handling."""
    params |= {"api_key": API_KEY, "format": "json"}
    try:
        response = requests.get(API_ROOT, params=params, headers=HEADERS, timeout=5)
        data = response.json()
        if "error" in data:
            raise RuntimeError(data["message"])
        return data
    except Exception as exc:  # pragma: no cover
        logging.warning("Last.fm API error: %s", exc)
        return None


# ------------------------------------------------------------------ Views
def home(request):
    """Render the top page with a simple track search form."""
    return render(request, "home.html")


def track_search(request):
    """Search tracks by keyword using Last.fm `track.search`."""
    query = request.GET.get("q")
    if not query:
        return redirect("home")
    data = call_lastfm({"method": "track.search", "track": query, "limit": 20})
    tracks = data["results"]["trackmatches"]["track"] if data else []
    return render(request, "search_results.html", {"query": query, "tracks": tracks})


def similar(request):
    """Fetch similar tracks for the given artist/track pair."""
    artist = request.GET.get("artist")
    track = request.GET.get("track")
    if not (artist and track):
        return redirect("home")
    data = call_lastfm(
        {
            "method": "track.getSimilar",
            "artist": artist,
            "track": track,
            "limit": 15,
        }
    )
    tracks = data["similartracks"]["track"] if data else []
    return render(
        request,
        "similar.html",
        {"base_track": f"{artist} – {track}", "tracks": tracks},
    )


def artist_detail(request, name: str):
    """Display artist information fed by `artist.getInfo`."""
    data = call_lastfm({"method": "artist.getInfo", "artist": name, "lang": "en"})
    return render(request, "artist.html", {"a": data and data["artist"], "name": name})


def live_chart(request):
    """Display the current global top tracks (Last.fm chart)."""
    data = call_lastfm({"method": "chart.getTopTracks", "limit": 25})
    tracks = data["tracks"]["track"] if data else []
    return render(request, "charts.html", {"tracks": tracks})
