"""
Views for the music app
────────────────────────────────────────────────────────────
外部 API:
  • Last.fm   – track / artist 情報・レコメンド取得
  • Spotify   – track ID を 1 件だけ検索（埋め込み用）
  • iTunes    – 30-sec preview（Spotify が無い場合の保険）
"""

from __future__ import annotations

import json
import logging
from typing import Any
from urllib.parse import unquote

import requests
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render

from .forms import AddTrackForm, PlaylistRenameForm, SignUpForm
from .models import Artist, Playlist, PlaylistTrack, Track

# ------------------------------------------------------------------ #
# Last.fm helper
# ------------------------------------------------------------------ #
LASTFM_KEY    = settings.LASTFM_API_KEY
LASTFM_ROOT   = settings.LASTFM_ROOT          # e.g. "https://ws.audioscrobbler.com/2.0/"
LASTFM_HEADER = {"User-Agent": settings.LASTFM_USER_AGENT}


def _lastfm(method: str, **params) -> dict | None:
    """Thin wrapper around Last.fm REST API – returns parsed JSON or None."""
    params |= {"method": method, "api_key": LASTFM_KEY, "format": "json"}
    try:
        r = requests.get(LASTFM_ROOT, params=params, headers=LASTFM_HEADER, timeout=5)
        data = r.json()
        if "error" in data:
            raise RuntimeError(data["message"])
        return data
    except Exception as exc:  # noqa: BLE001
        logging.warning("Last.fm API error: %s", exc)
        return None


# ------------------------------------------------------------------ #
# Spotify helper ―― 最低限の検索だけ
# ------------------------------------------------------------------ #
_SPOTIFY_TOKEN = getattr(settings, "SPOTIFY_TOKEN", None)  # Personal access token (短命)
_SPOTIFY_SEARCH = "https://api.spotify.com/v1/search"


def _spotify_search(q: str) -> dict | None:
    """
    Return first Spotify track JSON or None.

    - `settings.SPOTIFY_TOKEN` が無い/期限切れなら None を返す
    """
    if not _SPOTIFY_TOKEN:
        return None

    try:
        r = requests.get(
            _SPOTIFY_SEARCH,
            headers={"Authorization": f"Bearer {_SPOTIFY_TOKEN}"},
            params={"q": q, "type": "track", "limit": 1},
            timeout=5,
        )
        if r.status_code != 200:
            raise RuntimeError(f"HTTP {r.status_code}")
        items = r.json().get("tracks", {}).get("items", [])
        return items[0] if items else None
    except Exception as exc:  # noqa: BLE001
        logging.warning("Spotify API error: %s", exc)
        return None


# ------------------------------------------------------------------ #
# iTunes 30-sec preview helper – Spotify が無いときの保険
# ------------------------------------------------------------------ #
ITUNES_URL = "https://itunes.apple.com/search"


def itunes_preview(term: str) -> str | None:
    """Return previewUrl of first iTunes match (or None)."""
    try:
        r = requests.get(
            ITUNES_URL,
            params={"term": term, "entity": "song", "limit": 1},
            timeout=5,
        )
        data = r.json()
        if data.get("resultCount"):
            return data["results"][0]["previewUrl"]
    except Exception as exc:  # noqa: BLE001
        logging.warning("iTunes API error: %s", exc)
    return None


def ensure_preview(track: Track) -> None:
    """Track に preview_url が無ければ iTunes から取得して保存。"""
    if track.preview_url:
        return
    url = itunes_preview(f"{track.artist.name} {track.title}")
    if url:
        track.preview_url = url
        track.save(update_fields=["preview_url"])


# ------------------------------------------------------------------ #
# 共通ユーティリティ
# ------------------------------------------------------------------ #
def _double_unquote(value: str) -> str:
    """
    `%2520` → `%20` → `' '` のように
    2 回エンコードされている文字列を元に戻す。
    """
    return unquote(unquote(value))


# ------------------------------------------------------------------ #
# Public pages
# ------------------------------------------------------------------ #
def home(request):
    return render(request, "home.html")


def track_search(request):
    q = request.GET.get("q", "").strip()
    if not q:
        return redirect("home")

    data = _lastfm("track.search", track=q, limit=20) or {}
    tracks = data.get("results", {}).get("trackmatches", {}).get("track", [])
    if isinstance(tracks, dict):  # 1 件だけの場合は dict で返る
        tracks = [tracks]

    return render(request, "search_results.html", {"query": q, "tracks": tracks})


def live_chart(request):
    data = _lastfm("chart.getTopTracks", limit=25) or {}
    tracks = data.get("tracks", {}).get("track", [])
    return render(request, "charts.html", {"tracks": tracks})


def similar(request):
    art = request.GET.get("artist")
    title = request.GET.get("track")
    if not (art and title):
        return redirect("home")

    data = _lastfm("track.getSimilar", artist=art, track=title, limit=15) or {}
    tracks = data.get("similartracks", {}).get("track", [])
    if isinstance(tracks, dict):
        tracks = [tracks]

    return render(
        request,
        "similar.html",
        {"base_track": f"{art} – {title}", "tracks": tracks},
    )


def deepcut(request):
    art = request.GET.get("artist")
    title = request.GET.get("track")
    if not (art and title):
        return redirect("home")

    base = _lastfm("track.getInfo", artist=art, track=title) or {}
    base_play = int(base.get("track", {}).get("playcount", 1))

    sim = _lastfm("track.getSimilar", artist=art, track=title, limit=100) or {}
    candidates = sim.get("similartracks", {}).get("track", [])
    if isinstance(candidates, dict):
        candidates = [candidates]

    deep = [
        t for t in candidates
        if int(t.get("playcount", 0)) < 0.2 * base_play
           and int(t.get("playcount", 0)) < 50_000
    ][:15]

    return render(
        request,
        "deepcut.html",
        {"base_track": f"{art} – {title}", "tracks": deep},
    )


def artist_detail(request, name: str):
    data = _lastfm("artist.getInfo", artist=name, lang="en") or {}
    return render(request, "artist.html", {"a": data.get("artist"), "name": name})


def track_detail(request, artist: str, title: str):
    """
    /track/<artist>/<title>/ から個別曲ページ。

    テンプレート側で 1 回 URL-エンコード → Django reverse でさらに
    `%` が `%25` にエンコードされるため、ここでは 2 回 unquote する。
    """
    artist = _double_unquote(artist)
    title = _double_unquote(title)

    data = _lastfm("track.getInfo", artist=artist, track=title) or {}
    track = data.get("track")
    if not track:
        return render(request, "track_detail.html",
                      {"error": "Could not fetch track information."})

    sp = _spotify_search(f"artist:{artist} track:{title}")
    embed_url = f"https://open.spotify.com/embed/track/{sp['id']}" if sp else None

    return render(request, "track_detail.html",
                  {"track": track, "embed_url": embed_url})


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
# Playlist CRUD + reorder/delete
# ------------------------------------------------------------------ #
@login_required
def playlist_list(request):
    if request.method == "POST":
        delete_id = request.POST.get("delete_id")
        if delete_id:
            get_object_or_404(Playlist, pk=delete_id, owner=request.user).delete()

    playlists = request.user.playlists.all()
    return render(request, "playlist_list.html", {"playlists": playlists})


@login_required
def playlist_detail(request, pk: int):
    pl = get_object_or_404(Playlist, pk=pk, owner=request.user)

    # ---- 名前変更 ----
    if "rename" in request.POST:
        form = PlaylistRenameForm(request.POST, instance=pl)
        if form.is_valid():
            form.save()
            return redirect("playlist_detail", pk=pk)

    # ---- 曲削除 ----
    if "remove_track" in request.POST:
        PlaylistTrack.objects.filter(
            playlist=pl, track_id=request.POST["remove_track"]
        ).delete()

    # ---- 曲順並べ替え ----
    if "order" in request.POST:
        try:
            order = json.loads(request.POST["order"])
            for idx, track_id in enumerate(order):
                PlaylistTrack.objects.filter(
                    playlist=pl, track_id=track_id
                ).update(position=idx)
        except Exception:  # noqa: BLE001
            return HttpResponseBadRequest("Invalid order payload")

    # 最新状態
    pl.refresh_from_db()
    items = pl.items.select_related("track__artist")

    for item in items:  # preview の確保
        ensure_preview(item.track)

    ctx = {
        "playlist": pl,
        "tracks": items,
        "rename_form": PlaylistRenameForm(instance=pl),
    }
    return render(request, "playlist_detail.html", ctx)


@login_required
def add_to_playlist(request):
    form = AddTrackForm(request.user, request.POST)
    if not form.is_valid():
        return redirect("search")

    artist = request.POST.get("artist")
    title = request.POST.get("track")
    if not (artist and title):
        return redirect("search")

    # 既存 or 新規
    pl_choice = form.cleaned_data["playlist"]
    if pl_choice == "__new__":
        name = form.cleaned_data["new_name"] or "New Playlist"
        pl = Playlist.objects.create(owner=request.user, name=name)
    else:
        pl = get_object_or_404(Playlist, pk=pl_choice, owner=request.user)

    art, _ = Artist.objects.get_or_create(name=artist)
    track, _ = Track.objects.get_or_create(title=title, artist=art)
    PlaylistTrack.objects.get_or_create(
        playlist=pl, track=track, position=pl.items.count()
    )
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
