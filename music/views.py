"""
views.py – NextTrack (Deezer + GetSongBPM 版)

Spotify/MusicStax 依存を完全排除し、30-sec プレビューは Deezer
（fallback に iTunes）、Key/BPM は GetSongBPM API を利用。
"""

import json
import logging
import re
import urllib.parse
from typing import Any, Dict, Optional, Tuple

import requests
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AddTrackForm, PlaylistRenameForm, SignUpForm, VocalRangeForm
from .models import Artist, Playlist, PlaylistTrack, Track, VocalProfile
from .utils import youtube_id
from .itunes import itunes_preview
from .lastfm import top_tracks
from .deezer import search as dz_search            # Deezer preview / art
from .getsong import audio_features as gs_audio    # Key / BPM via GetSongBPM

# ------------------------------------------------------------------
# Logger
# ------------------------------------------------------------------
_log = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Last.fm helper
# ------------------------------------------------------------------
API_KEY = settings.LASTFM_API_KEY
API_ROOT = settings.LASTFM_ROOT
HEADERS = {"User-Agent": settings.LASTFM_USER_AGENT}


def _lastfm(method: str, **params):
    params["method"] = method
    return call_lastfm(params)


def call_lastfm(params: Dict[str, Any]) -> Optional[Dict]:
    """Wrapper for the Last.fm REST API, returns JSON or None on error."""
    params |= {"api_key": API_KEY, "format": "json"}
    try:
        res = requests.get(API_ROOT, params=params, headers=HEADERS, timeout=5)
        data = res.json()
        if "error" in data:
            raise RuntimeError(data["message"])
        return data
    except Exception as exc:
        _log.warning("Last.fm API error: %s", exc)
        return None


# ------------------------------------------------------------------
# 30-sec preview helper（iTunes Fallback）
# ------------------------------------------------------------------
def ensure_preview(track: Track):
    """If the Track lacks preview_url, fetch a 30-sec clip from iTunes and save it."""
    if track.preview_url:
        return
    url = itunes_preview(f"{track.artist.name} {track.title}")
    if url:
        track.preview_url = url
        track.save(update_fields=["preview_url"])


# ------------------------------------------------------------------
# Key → MIDI conversion table (C4 = 60)
# ------------------------------------------------------------------
_KEY2MIDI = {
    "C": 60, "C#": 61, "Db": 61, "D": 62, "D#": 63, "Eb": 63, "E": 64,
    "F": 65, "F#": 66, "Gb": 66, "G": 67, "G#": 68, "Ab": 68, "A": 69,
    "A#": 70, "Bb": 70, "B": 71,
}


def _estimate_pitch_range(feat: Optional[Dict]) -> Tuple[int, int]:
    """
    GetSongBPM が返す key から “主音～主音+1oct” を推定して返す。
    key が無い場合は C4–C5 を返す。
    """
    if not feat:
        return (60, 72)
    root = _KEY2MIDI.get((feat.get("key") or "").strip().upper())
    return (root, root + 12) if root is not None else (60, 72)


# ------------------------------------------------------------------
# Public pages
# ------------------------------------------------------------------
def home(request):
    return render(request, "home.html")


def track_search(request):
    """
    Last.fm で検索し、iTunes Preview / YouTube URL を付与した結果一覧を表示。
    """
    q = request.GET.get("q", "").strip()
    if not q:
        return redirect("home")

    page = int(request.GET.get("page", "1") or "1")
    sort = request.GET.get("sort", "default")

    data = _lastfm("track.search", track=q, limit=20, page=page) or {}
    tracks = data.get("results", {}).get("trackmatches", {}).get("track", [])
    if isinstance(tracks, dict):
        tracks = [tracks]

    if sort == "listeners":
        tracks.sort(key=lambda t: int(t.get("listeners", 0)), reverse=True)
    elif sort == "name":
        tracks.sort(key=lambda t: t.get("name", "").lower())

    total = int(data.get("results", {}).get("opensearch:totalResults", 0))
    has_next = page * 20 < total
    has_prev = page > 1

    for t in tracks:
        term = f"{t.get('artist')} {t.get('name')}"
        safe_key = re.sub(r"[^a-z0-9]", "_", term.lower())
        cache_key = "prev:" + safe_key

        cached = cache.get(cache_key) or {}
        if "apple" not in cached:
            cached["apple"] = itunes_preview(term)
        if "youtube" not in cached:
            vid = youtube_id(term)
            cached["youtube"] = (
                f"https://www.youtube.com/watch?v={vid}"
                if vid
                else f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(term)}"
            )
        cache.set(cache_key, cached, 60 * 60)
        t["apple_preview"] = cached["apple"]
        t["youtube_url"] = cached["youtube"]

    return render(
        request,
        "search_results.html",
        {
            "query": q,
            "tracks": tracks,
            "page": page,
            "sort": sort,
            "has_next": has_next,
            "has_prev": has_prev,
        },
    )


def similar(request):
    art, title = request.GET.get("artist"), request.GET.get("track")
    if not (art and title):
        return redirect("home")

    data = call_lastfm(
        {"method": "track.getSimilar", "artist": art, "track": title, "limit": 15}
    ) or {}
    tracks = data.get("similartracks", {}).get("track", [])
    if isinstance(tracks, dict):
        tracks = [tracks]

    for t in tracks:
        term = f"{t.get('artist', {}).get('name','')} {t.get('name','')}"
        safe_key = re.sub(r"[^a-z0-9]", "_", term.lower())
        cache_key = "prev:" + safe_key

        cached = cache.get(cache_key) or {}
        if "apple" not in cached:
            cached["apple"] = itunes_preview(term)
        if "youtube" not in cached:
            vid = youtube_id(term)
            cached["youtube"] = (
                f"https://www.youtube.com/watch?v={vid}"
                if vid
                else f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(term)}"
            )
        cache.set(cache_key, cached, 60 * 60)
        t["apple_preview"] = cached["apple"]
        t["youtube_url"] = cached["youtube"]

    ctx = {"base_track": f"{art} – {title}", "tracks": tracks}
    return render(request, "similar.html", ctx)


def live_chart(request):
    data = call_lastfm({"method": "chart.getTopTracks", "limit": 25}) or {}
    tracks = data.get("tracks", {}).get("track", [])
    if isinstance(tracks, dict):
        tracks = [tracks]

    for t in tracks:
        term = f"{t.get('artist', {}).get('name','')} {t.get('name','')}"
        safe_key = re.sub(r"[^a-z0-9]", "_", term.lower())
        cache_key = "prev:" + safe_key

        cached = cache.get(cache_key) or {}
        if "apple" not in cached:
            cached["apple"] = itunes_preview(term)
        if "youtube" not in cached:
            vid = youtube_id(term)
            cached["youtube"] = (
                f"https://www.youtube.com/watch?v={vid}"
                if vid
                else f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(term)}"
            )
        cache.set(cache_key, cached, 60 * 60)
        t["apple_preview"] = cached["apple"]
        t["youtube_url"] = cached["youtube"]

    return render(request, "charts.html", {"tracks": tracks})


def artist_detail(request, name: str):
    data = call_lastfm({"method": "artist.getInfo", "artist": name, "lang": "en"})
    return render(request, "artist.html", {"a": data and data["artist"], "name": name})


def track_detail(request, artist: str, title: str):
    info = call_lastfm({"method": "track.getInfo", "artist": artist, "track": title})
    if not info:
        return render(request, "track.html", {"title": None})

    term = f"{artist} {title}"
    safe_key = re.sub(r"[^a-z0-9]", "_", term.lower())
    cache_key = "prev:" + safe_key

    cached: Dict[str, Any] = cache.get(cache_key) or {}
    if "apple" not in cached:
        cached["apple"] = itunes_preview(term)
    if "youtube" not in cached:
        vid = youtube_id(term)
        cached["youtube"] = f"https://www.youtube.com/watch?v={vid}" if vid else None
    cache.set(cache_key, cached, 60 * 60)

    t = info["track"]
    ctx = {
        "title": t["name"],
        "artist": t["artist"]["name"],
        "url": t["url"],
        "playcount": int(t.get("playcount", 0)),
        "summary": t.get("wiki", {}).get("summary", ""),
        "apple_preview": cached["apple"],
        "youtube_url": cached["youtube"],
    }
    return render(request, "track.html", ctx)


# ------------------------------------------------------------------
# Deep-cut recommendation
# ------------------------------------------------------------------
def deepcut(request):
    art = request.GET.get("artist")
    title = request.GET.get("track")
    if not (art and title):
        return redirect("home")

    base = call_lastfm({"method": "track.getInfo", "artist": art, "track": title})
    if not base:
        return redirect("home")
    base_play = int(base["track"].get("playcount", 1))

    sim = call_lastfm(
        {"method": "track.getSimilar", "artist": art, "track": title, "limit": 100}
    ) or {}
    candidates = sim.get("similartracks", {}).get("track", [])
    if isinstance(candidates, dict):
        candidates = [candidates]

    deep = [
        t
        for t in candidates
        if int(t.get("playcount", 0)) < 0.2 * base_play
        and int(t.get("playcount", 0)) < 50_000
    ][:15]

    for t in deep:
        term = f"{t.get('artist', {}).get('name','')} {t.get('name','')}"
        safe_key = re.sub(r"[^a-z0-9]", "_", term.lower())
        cache_key = "prev:" + safe_key

        cached = cache.get(cache_key) or {}
        if "apple" not in cached:
            cached["apple"] = itunes_preview(term)
        if "youtube" not in cached:
            vid = youtube_id(term)
            cached["youtube"] = (
                f"https://www.youtube.com/watch?v={vid}"
                if vid
                else f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(term)}"
            )
        cache.set(cache_key, cached, 60 * 60)
        t["apple_preview"] = cached["apple"]
        t["youtube_url"] = cached["youtube"]

    return render(
        request,
        "deepcut.html",
        {"base_track": f"{art} – {title}", "tracks": deep},
    )


# ------------------------------------------------------------------
# Sign-up
# ------------------------------------------------------------------
def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("home")
    else:
        form = SignUpForm()
    return render(request, "registration/signup.html", {"form": form})


# ------------------------------------------------------------------
# Playlist CRUD + reorder/delete
# ------------------------------------------------------------------
@login_required
def playlist_list(request):
    """GET: list playlists  •  POST: delete playlist"""
    if request.method == "POST":
        delete_id = request.POST.get("delete_id")
        if delete_id:
            get_object_or_404(Playlist, pk=delete_id, owner=request.user).delete()
    playlists = request.user.playlists.all()
    return render(request, "playlist_list.html", {"playlists": playlists})


@login_required
def playlist_detail(request, pk: int):
    """Display, rename, delete tracks, reorder and ensure preview."""
    pl = get_object_or_404(Playlist, pk=pk, owner=request.user)

    # Rename
    if "rename" in request.POST:
        form = PlaylistRenameForm(request.POST, instance=pl)
        if form.is_valid():
            form.save()
        return redirect("playlist_detail", pk=pk)

    # Delete track
    if "remove_track" in request.POST:
        PlaylistTrack.objects.filter(playlist=pl, track_id=request.POST["remove_track"]).delete()

    # Reorder
    if "order" in request.POST:
        try:
            order = json.loads(request.POST["order"])
            for idx, track_id in enumerate(order):
                PlaylistTrack.objects.filter(playlist=pl, track_id=track_id).update(position=idx)
        except Exception:
            return HttpResponseBadRequest("Invalid order payload")

    pl.refresh_from_db()
    items = pl.items.select_related("track__artist")

    for item in items:
        ensure_preview(item.track)

    ctx = {
        "playlist": pl,
        "tracks": items,
        "rename_form": PlaylistRenameForm(instance=pl),
    }
    return render(request, "playlist_detail.html", ctx)


@login_required
def add_to_playlist(request):
    """POST back from search_results to add track to playlist or new playlist."""
    form = AddTrackForm(request.user, request.POST)
    if not form.is_valid():
        return redirect("search")

    artist = request.POST.get("artist")
    title = request.POST.get("track")
    if not (artist and title):
        return redirect("search")

    pl_choice = form.cleaned_data["playlist"]
    if pl_choice == "__new__":
        name = form.cleaned_data["new_name"] or "New Playlist"
        pl = Playlist.objects.create(owner=request.user, name=name)
    else:
        pl = get_object_or_404(Playlist, pk=pl_choice, owner=request.user)

    art, _ = Artist.objects.get_or_create(name=artist)
    track, _ = Track.objects.get_or_create(title=title, artist=art)
    PlaylistTrack.objects.get_or_create(playlist=pl, track=track, position=pl.items.count())
    ensure_preview(track)
    return redirect("playlist_detail", pk=pl.pk)


@login_required
def playlist_create(request):
    if request.method == "POST":
        name = request.POST.get("name") or "New Playlist"
        Playlist.objects.create(owner=request.user, name=name)
    return redirect("playlist_list")


@login_required
def remove_from_playlist(request, pk: int, track_id: int):
    pl = get_object_or_404(Playlist, pk=pk, owner=request.user)
    PlaylistTrack.objects.filter(playlist=pl, track_id=track_id).delete()
    return redirect("playlist_detail", pk=pk)


# ------------------------------------------------------------------
# Vocal recommendation – Key & Tempo filter
# ------------------------------------------------------------------
@login_required
def vocal_recommend(request):
    """
    GetSongBPM の key / tempo とユーザー声域を使ってレコメンド。
    * 主音が声域内にある  * BPM が bpm_min–bpm_max に収まる
    """

    profile, _ = VocalProfile.objects.get_or_create(
        user=request.user, defaults={"note_min": 60, "note_max": 72}
    )

    # テンポ範囲（URL パラメータで上書き可）
    bpm_min = int(request.GET.get("bpm_min", 70))
    bpm_max = int(request.GET.get("bpm_max", 150))
    if bpm_min > bpm_max:
        bpm_min, bpm_max = bpm_max, bpm_min

    sort  = request.GET.get("sort", "default")   # default|listeners|name|tempo
    page  = int(request.GET.get("page", "1"))
    per   = 20

    candidates = top_tracks(limit=80)
    reco: list[Dict] = []

    for tr in candidates:
        term = f"{tr['artist']} {tr['title']}"

        # Deezer preview
        dz_hit = dz_search(term, limit=1)
        preview = dz_hit[0].get("preview_url") if dz_hit else itunes_preview(term)

        # Key / Tempo
        feat = gs_audio(query=term)
        if not feat or not feat.get("key") or not feat.get("tempo"):
            continue

        key_name = feat["key"].upper()
        tempo    = feat["tempo"]
        root     = _KEY2MIDI.get(key_name)
        if root is None:
            continue

        # フィルタ
        if not (profile.note_min <= root <= profile.note_max):
            continue
        if not (bpm_min <= tempo <= bpm_max):
            continue

        tr.update(
            key=key_name,
            tempo=tempo,
            apple_preview=preview,
            youtube_url=f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(term)}",
        )
        reco.append(tr)

    # ソート
    if sort == "listeners":
        reco.sort(key=lambda x: -x.get("playcount", 0))
    elif sort == "name":
        reco.sort(key=lambda x: x["title"].lower())
    elif sort == "tempo":
        reco.sort(key=lambda x: x["tempo"])

    start, end = (page - 1) * per, page * per
    context = {
        "tracks": reco[start:end],
        "page": page,
        "has_next": end < len(reco),
        "has_prev": start > 0,
        "sort": sort,
        "bpm_min": bpm_min,
        "bpm_max": bpm_max,
        "profile": profile,
    }
    return render(request, "vocal_recommend.html", context)
