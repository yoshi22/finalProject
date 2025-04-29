import logging, json, re, urllib.parse
from typing import Any

import requests
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.http import HttpResponseBadRequest

from .forms import (
    SignUpForm,
    PlaylistRenameForm,
    AddTrackForm,
    VocalRangeForm,
)
from .models import Artist, Playlist, PlaylistTrack, Track, VocalProfile
from django.core.cache import cache

from .utils import youtube_id
from .itunes import itunes_preview
from .lastfm import top_tracks
from .utils_spotify import spotify_id, pitch_range  # ★ Spotify helper

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
# 30-sec preview helper（Track オブジェクト向け）
# ------------------------------------------------------------------
def ensure_preview(track: Track):
    """Track.preview_url が空なら iTunes Search で 30 秒プレビューを取得して保存"""
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


# ----------（中略）既存の search/similar/live_chart/playlist 系ビューはそのまま ----------


# ------------------------------------------------------------------
# Vocal range–aware recommendation
# ------------------------------------------------------------------
@login_required
def vocal_recommend(request):
    """
    1. ユーザーが最低音/最高音をフォーム入力 → VocalProfile を保存
    2. 音域が登録済みなら Last.fm チャート曲を Spotify Audio-Analysis で
       メロディ音域推定し、範囲内の曲だけを表示
    """
    # ---- ① プロファイル取得・保存 ---------------------------------
    try:
        profile = VocalProfile.objects.get(user=request.user)
    except VocalProfile.DoesNotExist:
        profile = None

    if request.method == "POST":
        # 既存があれば上書き、無ければ新規インスタンスで保存
        form = VocalRangeForm(request.POST, instance=profile or VocalProfile(user=request.user))
        if form.is_valid():
            profile = form.save()
            return redirect("vocal_recommend")
    else:
        form = VocalRangeForm(instance=profile)

    # プロファイル未登録ならフォームだけ表示
    if not profile:
        return render(request, "vocal_recommend.html", {"form": form, "tracks": []})

    # ---- ② 候補曲プール --------------------------------------------
    candidates = top_tracks(limit=200)  # [{'artist':..,'title':..,'playcount':..}, …]
    reco: list[dict] = []

    for tr in candidates:
        spid = spotify_id(tr["artist"], tr["title"])
        if not spid:
            continue
        pr = pitch_range(spid)
        if not pr:
            continue
        lo, hi = pr
        if profile.note_min <= lo and hi <= profile.note_max:
            tr |= {
                "spotify_id":  spid,
                "pitch_low":   lo,
                "pitch_high":  hi,
            }
            # YouTube full link
            vid = youtube_id(f"{tr['artist']} {tr['title']}")
            if vid:
                tr["youtube_url"] = f"https://www.youtube.com/watch?v={vid}"
            reco.append(tr)

    # 人気順（playcount 降順）
    reco.sort(key=lambda x: -x.get("playcount", 0))

    return render(
        request,
        "vocal_recommend.html",
        {"form": form, "tracks": reco[:50]},
    )
