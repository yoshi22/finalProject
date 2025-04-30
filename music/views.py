import json
import logging
import re
import urllib.parse
from typing import Any

import requests
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.core.cache import cache

from .forms import AddTrackForm, PlaylistRenameForm, SignUpForm, VocalRangeForm
from .models import Artist, Playlist, PlaylistTrack, Track, VocalProfile
from .utils import youtube_id
from .itunes import itunes_preview            # 外部モジュールで定義
from .lastfm import top_tracks
from .spotify import spotify_id, pitch_range  # 置き場所に合わせて import

# ------------------------------------------------------------------
# Last.fm helper
# ------------------------------------------------------------------
API_KEY = settings.LASTFM_API_KEY
API_ROOT = settings.LASTFM_ROOT
HEADERS = {"User-Agent": settings.LASTFM_USER_AGENT}


def _lastfm(method: str, **params):
    params["method"] = method
    return call_lastfm(params)


def call_lastfm(params: dict[str, Any]) -> dict | None:
    """Wrapper for the Last.fm REST API, returns JSON or None on error."""
    params |= {"api_key": API_KEY, "format": "json"}
    try:
        res = requests.get(API_ROOT, params=params, headers=HEADERS, timeout=5)
        data = res.json()
        if "error" in data:
            raise RuntimeError(data["message"])
        return data
    except Exception as exc:
        logging.warning("Last.fm API error: %s", exc)
        return None


# ------------------------------------------------------------------
# 30-sec  preview helper
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
# Public pages
# ------------------------------------------------------------------
def home(request):
    return render(request, "home.html")


def track_search(request):
    q = request.GET.get("q", "").strip()
    if not q:
        return redirect("home")

    # pagination & sort
    page = int(request.GET.get("page", "1") or "1")          # ?page=
    sort = request.GET.get("sort", "default")                # ?sort=default|listeners|name

    data = _lastfm("track.search", track=q, limit=20, page=page) or {}
    tracks = data.get("results", {}).get("trackmatches", {}).get("track", [])
    if isinstance(tracks, dict):
        tracks = [tracks]

    # client-side sorting
    if sort == "listeners":
        tracks.sort(key=lambda t: int(t.get("listeners", 0)), reverse=True)
    elif sort == "name":
        tracks.sort(key=lambda t: t.get("name", "").lower())

    # next/prev page flags
    total = int(data.get("results", {}).get("opensearch:totalResults", 0))
    has_next = page * 20 < total
    has_prev = page > 1

    # attach previews
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

    cached: dict[str, Any] = cache.get(cache_key) or {}
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
    """GET: list playlists  POST: delete playlist"""
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

    # Existing vs new playlist
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
# Vocal recommendation
# ------------------------------------------------------------------
@login_required
def vocal_recommend(request):
# ---- ①  音域入力 / プロファイル取得 --------------------------
    defaults = {"note_min": 60, "note_max": 72}
    profile, _ = VocalProfile.objects.get_or_create(
        user=request.user, defaults=defaults
    )

    if request.method == "POST":
        form = VocalRangeForm(request.POST, instance=profile)
        if form.is_valid():
            form.save()
            return redirect("vocal_recommend")
    else:
        form = VocalRangeForm(instance=profile)

    # ---- ②  候補曲プール ----------------------------------------
    candidates = top_tracks(limit=200)
    reco = []
    for tr in candidates:
        spid = spotify_id(tr["artist"], tr["title"])
        if not spid:
            continue

        pr = pitch_range(spid) or (60, 72)     # ←★★ fallback
        lo, hi = pr
        if profile.note_min <= lo and hi <= profile.note_max:
            tr.update(
                spotify_id=spid,
                pitch_low=lo,
                pitch_high=hi,
                youtube_url=f"https://www.youtube.com/watch?v={youtube_id(tr['artist']+' '+tr['title'])}"
            )
            reco.append(tr)

    reco.sort(key=lambda x: -x.get("playcount", 0))
    return render(request, "vocal_recommend.html",
                {"form": form, "tracks": reco[:50]})
