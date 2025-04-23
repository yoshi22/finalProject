import logging
import math
from typing import Any

import requests
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .models import Artist, Playlist, PlaylistTrack, Track

# ------------------------------------------------------------------ #
#  Last.fm helper
# ------------------------------------------------------------------ #
API_KEY = settings.LASTFM_API_KEY
API_ROOT = settings.LASTFM_ROOT
HEADERS = {"User-Agent": settings.LASTFM_USER_AGENT}


def call_lastfm(params: dict[str, Any]) -> dict | None:
    """Generic Last.fm GET with basic error handling."""
    params |= {"api_key": API_KEY, "format": "json"}
    try:
        res = requests.get(API_ROOT, params=params, headers=HEADERS, timeout=5)
        data = res.json()
        if "error" in data:
            raise RuntimeError(data["message"])
        return data
    except Exception as exc:  # pragma: no cover
        logging.warning("Last.fm API error: %s", exc)
        return None


# ------------------------------------------------------------------ #
#  YouTube helper (search + first video)
# ------------------------------------------------------------------ #
YT_KEY = settings.YOUTUBE_API_KEY
YT_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"


def search_youtube(query: str) -> str | None:
    if not YT_KEY:
        return None
    params = {
        "part": "id",
        "type": "video",
        "maxResults": 1,
        "q": query,
        "key": YT_KEY,
    }
    try:
        res = requests.get(YT_SEARCH_URL, params=params, timeout=5)
        data = res.json()
        items = data.get("items")
        if items:
            return items[0]["id"]["videoId"]
    except Exception as exc:
        logging.warning("YouTube API error: %s", exc)
    return None


# ------------------------------------------------------------------ #
#  Basic search / similar / chart
# ------------------------------------------------------------------ #
def home(request):
    return render(request, "home.html")


def track_search(request):
    q = request.GET.get("q")
    if not q:
        return redirect("home")
    data = call_lastfm({"method": "track.search", "track": q, "limit": 20})
    tracks = data["results"]["trackmatches"]["track"] if data else []
    return render(request, "search_results.html", {"query": q, "tracks": tracks})


def similar(request):
    art, title = request.GET.get("artist"), request.GET.get("track")
    if not (art and title):
        return redirect("home")
    data = call_lastfm(
        {"method": "track.getSimilar", "artist": art, "track": title, "limit": 15}
    )
    tracks = data["similartracks"]["track"] if data else []
    return render(
        request, "similar.html", {"base_track": f"{art} – {title}", "tracks": tracks}
    )


def artist_detail(request, name):
    data = call_lastfm({"method": "artist.getInfo", "artist": name, "lang": "en"})
    return render(request, "artist.html", {"a": data and data["artist"], "name": name})


def live_chart(request):
    data = call_lastfm({"method": "chart.getTopTracks", "limit": 25})
    tracks = data["tracks"]["track"] if data else []
    return render(request, "charts.html", {"tracks": tracks})


# ------------------------------------------------------------------ #
#  Track detail + YouTube embed
# ------------------------------------------------------------------ #
def track_detail(request, artist: str, title: str):
    info = call_lastfm({"method": "track.getInfo", "artist": artist, "track": title})
    if not info:
        return render(request, "track.html", {"title": None})

    t = info["track"]
    query = f"{artist} {title}"
    video_id = search_youtube(query)

    context = {
        "title": t["name"],
        "artist": t["artist"]["name"],
        "url": t["url"],
        "playcount": int(t.get("playcount", 0)),
        "summary": t.get("wiki", {}).get("summary", ""),
        "video_id": video_id,
        "query": query,
    }
    return render(request, "track.html", context)


# ------------------------------------------------------------------ #
#  Playlist CRUD
# ------------------------------------------------------------------ #
@login_required
def playlist_list(request):
    return render(request, "playlist_list.html", {"playlists": request.user.playlists.all()})


@login_required
def playlist_create(request):
    if request.method == "POST":
        name = request.POST.get("name")
        if name:
            Playlist.objects.create(owner=request.user, name=name)
        return redirect("playlist_list")
    return render(request, "playlist_create.html")


@login_required
def playlist_detail(request, pk):
    pl = get_object_or_404(Playlist, pk=pk, owner=request.user)
    return render(request, "playlist_detail.html", {"playlist": pl})


@login_required
def add_to_playlist(request, pk):
    pl = get_object_or_404(Playlist, pk=pk, owner=request.user)
    artist = request.GET.get("artist")
    title = request.GET.get("track")
    if not (artist and title):
        return redirect("playlist_detail", pk=pk)
    art_obj, _ = Artist.objects.get_or_create(name=artist)
    track_obj, _ = Track.objects.get_or_create(title=title, artist=art_obj)
    PlaylistTrack.objects.get_or_create(
        playlist=pl, track=track_obj, position=pl.items.count()
    )
    return redirect("playlist_detail", pk=pk)


@login_required
def remove_from_playlist(request, pk, track_id):
    pl = get_object_or_404(Playlist, pk=pk, owner=request.user)
    PlaylistTrack.objects.filter(playlist=pl, track_id=track_id).delete()
    return redirect("playlist_detail", pk=pk)
