import logging, json
from typing import Any

import requests
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponseBadRequest

from .forms import SignUpForm, PlaylistRenameForm, AddTrackForm
from .models import Artist, Playlist, PlaylistTrack, Track

# ------------------------------------------------------------------ #
# Last.fm helper
# ------------------------------------------------------------------ #
API_KEY = settings.LASTFM_API_KEY
API_ROOT = settings.LASTFM_ROOT
HEADERS = {"User-Agent": settings.LASTFM_USER_AGENT}


def call_lastfm(params: dict[str, Any]) -> dict | None:
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

def ensure_preview(track: Track):
    """Track に preview_url が無ければ iTunes から取得して保存"""
    if track.preview_url:
        return
    url = itunes_preview(f"{track.artist.name} {track.title}")
    if url:
        track.preview_url = url
        track.save(update_fields=["preview_url"])


# ------------------------------------------------------------------ #
# iTunes 30-sec preview helper
# ------------------------------------------------------------------ #
ITUNES_URL = "https://itunes.apple.com/search"


def itunes_preview(term: str) -> str | None:
    """Return previewUrl of first iTunes match (or None)."""
    try:
        r = requests.get(ITUNES_URL, params={"term": term, "entity": "song", "limit": 1}, timeout=5)
        data = r.json()
        if data.get("resultCount"):
            return data["results"][0]["previewUrl"]
    except Exception as exc:
        logging.warning("iTunes API error: %s", exc)
    return None


# ------------------------------------------------------------------ #
# Public pages
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
    data = call_lastfm({"method": "track.getSimilar", "artist": art, "track": title, "limit": 15})
    tracks = data["similartracks"]["track"] if data else []
    return render(request, "similar.html", {"base_track": f"{art} – {title}", "tracks": tracks})


def live_chart(request):
    data = call_lastfm({"method": "chart.getTopTracks", "limit": 25})
    tracks = data["tracks"]["track"] if data else []
    return render(request, "charts.html", {"tracks": tracks})


def artist_detail(request, name: str):
    data = call_lastfm({"method": "artist.getInfo", "artist": name, "lang": "en"})
    return render(request, "artist.html", {"a": data and data["artist"], "name": name})


def track_detail(request, artist: str, title: str):
    info = call_lastfm({"method": "track.getInfo", "artist": artist, "track": title})
    if not info:
        return render(request, "track.html", {"title": None})
    t = info["track"]
    preview = itunes_preview(f"{artist} {title}")
    ctx = {
        "title": t["name"],
        "artist": t["artist"]["name"],
        "url": t["url"],
        "playcount": int(t.get("playcount", 0)),
        "summary": t.get("wiki", {}).get("summary", ""),
        "preview": preview,
    }
    return render(request, "track.html", ctx)


# ------------------------------------------------------------------ #
# Sign-up
# ------------------------------------------------------------------ #
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


# ------------------------------------------------------------------ #
#  Playlist CRUD + reorder/delete
# ------------------------------------------------------------------ #
@login_required
def playlist_list(request):
    """
    GET  : 自分のプレイリスト一覧を表示
    POST : hidden フィールド delete_id を受け取ったらそのプレイリストを削除
    """
    if request.method == "POST":
        delete_id = request.POST.get("delete_id")
        if delete_id:
            get_object_or_404(Playlist, pk=delete_id, owner=request.user).delete()

    playlists = request.user.playlists.all()
    return render(request, "playlist_list.html", {"playlists": playlists})


@login_required
def playlist_detail(request, pk: int):
    """表示 + 名前変更 + 曲削除 + 並べ替え + 各曲の preview 確保"""
    pl = get_object_or_404(Playlist, pk=pk, owner=request.user)

    # ---------- プレイリスト名変更 ----------
    if "rename" in request.POST:
        form = PlaylistRenameForm(request.POST, instance=pl)
        if form.is_valid():
            form.save()
            return redirect("playlist_detail", pk=pk)

    # ---------- 曲削除 ----------
    if "remove_track" in request.POST:
        PlaylistTrack.objects.filter(
            playlist=pl, track_id=request.POST["remove_track"]
        ).delete()

    # ---------- 曲順並べ替え ----------
    if "order" in request.POST:
        try:
            order = json.loads(request.POST["order"])
            for idx, track_id in enumerate(order):
                PlaylistTrack.objects.filter(
                    playlist=pl, track_id=track_id
                ).update(position=idx)
        except Exception:
            return HttpResponseBadRequest("Invalid order payload")

    # 最新状態を取得
    pl.refresh_from_db()
    items = pl.items.select_related("track__artist")

    # ---------- 30-sec preview を確実に用意 ----------
    for item in items:
        ensure_preview(item.track)

    context = {
        "playlist": pl,
        "tracks": items,
        "rename_form": PlaylistRenameForm(instance=pl),
    }
    return render(request, "playlist_detail.html", context)


@login_required
def add_to_playlist(request):
    """POST from search_results: choose existing or create new playlist."""
    form = AddTrackForm(request.user, request.POST)
    if not form.is_valid():
        return redirect("search")  # fallback

    artist = request.POST.get("artist")
    title = request.POST.get("track")
    if not (artist and title):
        return redirect("search")

    # 既存 or 新規プレイリスト
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
    """Create a new playlist then redirect to list."""
    if request.method == "POST":
        name = request.POST.get("name") or "New Playlist"
        Playlist.objects.create(owner=request.user, name=name)
    return redirect("playlist_list")

@login_required
def remove_from_playlist(request, pk: int, track_id: int):
    """Delete a single track from the playlist, then redirect back."""
    pl = get_object_or_404(Playlist, pk=pk, owner=request.user)
    PlaylistTrack.objects.filter(playlist=pl, track_id=track_id).delete()
    return redirect("playlist_detail", pk=pk)
