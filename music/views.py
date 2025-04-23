import requests, logging
from django.conf import settings
from django.shortcuts import render, redirect

API_KEY = settings.LASTFM_API_KEY
API_ROOT = settings.LASTFM_ROOT
HEADERS  = {"User-Agent": settings.LASTFM_USER_AGENT}

def lfm(params):
    """汎用 Last.fm GET（簡易 5 秒タイムアウト）"""
    params |= {"api_key": API_KEY, "format": "json"}
    try:
        r = requests.get(API_ROOT, params=params, headers=HEADERS, timeout=5)
        data = r.json()
        if "error" in data:
            raise RuntimeError(data["message"])
        return data
    except Exception as e:
        logging.warning("Last.fm API error: %s", e)
        return None

# --- View 関数 -------------------------------------------------------------

def home(request):
    """検索フォームのみ"""
    return render(request, "home.html")

def track_search(request):
    """曲名検索 → 候補表示"""
    query = request.GET.get("q")
    if not query:
        return redirect("home")
    data = lfm({"method": "track.search", "track": query, "limit": 20})
    tracks = data["results"]["trackmatches"]["track"] if data else []
    return render(request, "search_results.html",
                  {"query": query, "tracks": tracks})

def similar(request):
    """曲名 + アーティストを受け取り類似曲を API から取得"""
    artist = request.GET.get("artist")
    track  = request.GET.get("track")
    if not (artist and track):
        return redirect("home")
    data = lfm({"method": "track.getSimilar",
                "artist": artist, "track": track, "limit": 15})
    tracks = data["similartracks"]["track"] if data else []
    return render(request, "similar.html",
                  {"base_track": f"{artist} – {track}", "tracks": tracks})

def artist_detail(request, name):
    data = lfm({"method": "artist.getInfo", "artist": name, "lang": "ja"})
    return render(request, "artist.html",
                  {"a": data and data["artist"], "name": name})

def live_chart(request):
    data = lfm({"method": "chart.getTopTracks", "limit": 25})
    tracks = data["tracks"]["track"] if data else []
    return render(request, "charts.html", {"tracks": tracks})
