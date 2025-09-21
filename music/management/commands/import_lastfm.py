import logging
from typing import Any, Optional

import requests
from django.conf import settings
from django.core.management.base import BaseCommand

from music.models import Artist, Track

API = settings.LASTFM_ROOT
KEY = settings.LASTFM_API_KEY
HEAD = {"User-Agent": settings.LASTFM_USER_AGENT}


def lfm(params: dict[str, Any]) -> dict | None:
    """Call Last.fm API and return JSON (or None on error)."""
    params |= {"api_key": KEY, "format": "json"}
    try:
        res = requests.get(API, params=params, headers=HEAD, timeout=5)
        data = res.json()
        if "error" in data:
            raise RuntimeError(data["message"])
        return data
    except Exception as exc:
        logging.warning("Last.fm API error: %s", exc)
        return None


class Command(BaseCommand):
    """Import artists / tracks from Last.fm into SQLite."""

    help = "Import chart or similar-track data from Last.fm"

    def add_arguments(self, parser):
        parser.add_argument("--artist", help="Seed artist name")
        parser.add_argument("--track", help="Seed track name (optional)")
        parser.add_argument("--chart", action="store_true", help="Import global top chart")

    # ------------------------------------------------------------------
    def handle(self, *args, **opts):
        if opts["chart"]:
            self.import_chart()
            return
        if not opts["artist"]:
            self.stderr.write("Use --artist or --chart.")
            return
        self.import_artist(opts["artist"], opts.get("track"))

    # ------------------------------------------------------------------
    def import_artist(self, artist_name: str, seed_track: Optional[str]):
        self.stdout.write(f"Fetching artist info: {artist_name}")
        a_data = lfm({"method": "artist.getInfo", "artist": artist_name})
        if not a_data:
            self.stderr.write("Failed to fetch artist.")
            return
        a_json = a_data["artist"]
        artist, _ = Artist.objects.update_or_create(
            name=a_json["name"],
            defaults={
                "mbid": a_json.get("mbid") or None,
                "url": a_json["url"],
                "listeners": a_json["stats"]["listeners"],
                "playcount": a_json["stats"]["playcount"],
                "summary": a_json["bio"]["summary"],
            },
        )
        source_track = seed_track or a_json["name"]
        s_data = lfm(
            {
                "method": "track.getSimilar",
                "artist": artist_name,
                "track": source_track,
                "limit": 20,
            }
        )
        if s_data:
            for t in s_data["similartracks"]["track"]:
                Track.objects.update_or_create(
                    title=t["name"],
                    artist=Artist.objects.get_or_create(name=t["artist"]["name"])[0],
                    defaults={
                        "url": t["url"],
                        "match": float(t["match"]),
                    },
                )
        self.stdout.write(self.style.SUCCESS("Import completed."))

    # ------------------------------------------------------------------
    def import_chart(self):
        self.stdout.write("Fetching global chart …")
        data = lfm({"method": "chart.getTopTracks", "limit": 50})
        if not data:
            self.stderr.write("Failed to fetch chart.")
            return
        for t in data["tracks"]["track"]:
            artist, _ = Artist.objects.get_or_create(
                name=t["artist"]["name"], defaults={"url": t["artist"]["url"]}
            )
            Track.objects.update_or_create(
                title=t["name"],
                artist=artist,
                defaults={
                    "url": t["url"],
                    "playcount": int(t["playcount"]),
                },
            )
        self.stdout.write(self.style.SUCCESS("Chart import completed."))
