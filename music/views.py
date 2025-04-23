import requests, logging
from django.conf import settings
from django.shortcuts import render, redirect
from django.core.cache import cache  # ★簡易キャッシュ
from music.models import Track


API = settings.LASTFM_ROOT
KEY = settings.LASTFM_API_KEY
HEAD = {"User-Agent": "NextTrackStudent/1.0"}  # 推奨ヘッダ

def _api(params, ttl=3600):
    """共通 GET + キャッシュ"""
    params |= {"api_key": KEY, "format": "json"}
    cache_key = f"lfm:{str(sorted(params.items()))}"
    if (data := cache.get(cache_key)):
        return data
    try:
        r = requests.get(API, params=params, headers=HEAD, timeout=5)
        data = r.json()
        if "error" in data: raise ValueError(data["message"])
        cache.set(cache_key, data, ttl)
        return data
    except Exception as e:
        logging.warning("Last.fm API error: %s", e)
        return None

# ① ホーム
def home(request):
    return render(request, "home.html")

# ② 類似曲
def similar(request):
    artist = request.GET.get("artist")
    track = request.GET.get("track")
    if not (artist and track):
        return redirect("home")

    data = _api({"method":"track.getSimilar",
                 "artist":artist, "track":track, "limit":10})
    tracks = (data or {}).get("similartracks", {}).get("track", [])
    return render(request, "similar.html",
                  {"base_track": f"{artist} – {track}", "tracks": tracks})

# ③ アーティスト詳細
def artist_detail(request, name):
    data = _api({"method":"artist.getInfo", "artist":name, "lang":"ja"}, ttl=86400)
    return render(request, "artist.html", {"a": data and data["artist"]})

# ④ トップチャート
def top_tracks(request):
    data = _api({"method":"chart.getTopTracks", "limit":20}, ttl=1800)
    tracks = (data or {}).get("tracks", {}).get("track", [])
    return render(request, "charts.html", {"tracks": tracks})

def charts_from_db(request):
    tracks = Track.objects.filter(playcount__gt=0).select_related("artist")[:20]
    return render(request, "charts.html", {"tracks": tracks})
