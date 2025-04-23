import logging
import math
import requests
from collections import Counter
from typing import Any

from django.conf import settings
from django.shortcuts import render, redirect

# ------------------------------------------------------------------ #
#  Last.fm API helper
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
#  Standard views (search / similar / artist / chart)
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


def artist_detail(request, name: str):
    data = call_lastfm({"method": "artist.getInfo", "artist": name, "lang": "en"})
    return render(request, "artist.html", {"a": data and data["artist"], "name": name})


def live_chart(request):
    data = call_lastfm({"method": "chart.getTopTracks", "limit": 25})
    tracks = data["tracks"]["track"] if data else []
    return render(request, "charts.html", {"tracks": tracks})


# ------------------------------------------------------------------ #
#  New: Deep-Cut recommendation view
# ------------------------------------------------------------------ #
def recommend(request):
    """Recommend lesser-known yet similar tracks (tag-hybrid scoring)."""
    seed_artist = request.GET.get("artist")
    seed_title = request.GET.get("track")
    if not (seed_artist and seed_title):
        return redirect("home")

    # (1) initial similar list
    sim_json = call_lastfm(
        {
            "method": "track.getSimilar",
            "artist": seed_artist,
            "track": seed_title,
            "limit": 100,
        }
    )
    if not sim_json:
        return render(
            request,
            "recommend.html",
            {"base": f"{seed_artist} – {seed_title}", "recs": []},
        )

    # seed track tags
    seed_info = call_lastfm(
        {"method": "track.getInfo", "artist": seed_artist, "track": seed_title}
    )
    seed_tags = {
        tag["name"] for tag in seed_info["track"]["toptags"]["tag"]
    } if seed_info else set()

    recs: list[dict[str, Any]] = []

    # (2) evaluate first 50 candidates to save quota
    for t in sim_json["similartracks"]["track"][:50]:
        cand_artist = t["artist"]["name"]
        cand_title = t["name"]
        info = call_lastfm(
            {"method": "track.getInfo", "artist": cand_artist, "track": cand_title}
        )
        if not info:
            continue
        cand = info["track"]
        playcount = int(cand.get("playcount", 0))
        tags = {tg["name"] for tg in cand.get("toptags", {}).get("tag", [])}

        # (3) score components
        match_score = float(t["match"])  # 0-1
        tag_score = len(seed_tags & tags) / (len(seed_tags) or 1)  # 0-1
        pop_penalty = math.log10(playcount + 10) / 7  # ≒0-1  (10→0, 10M→1)

        score = 0.6 * match_score + 0.4 * tag_score - 0.3 * pop_penalty
        recs.append(
            {
                "title": cand_title,
                "artist": cand_artist,
                "url": cand["url"],
                "score": round(score, 3),
                "playcount": playcount,
            }
        )

    # (4) top 10
    recs = sorted(recs, key=lambda x: x["score"], reverse=True)[:10]
    return render(
        request,
        "recommend.html",
        {"base": f"{seed_artist} – {seed_title}", "recs": recs},
    )
