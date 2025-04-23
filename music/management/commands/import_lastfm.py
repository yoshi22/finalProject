import requests, logging
from django.core.management.base import BaseCommand
from django.conf import settings
from music.models import Artist, Track

API = settings.LASTFM_ROOT
KEY = settings.LASTFM_API_KEY
HEAD = {"User-Agent": settings.LASTFM_USER_AGENT}

def call_lastfm(params):
    params |= {"api_key": KEY, "format": "json"}
    r = requests.get(API, params=params, headers=HEAD, timeout=5)
    data = r.json()
    if "error" in data:
        raise RuntimeError(data["message"])
    return data

class Command(BaseCommand):
    help = "Fetch artist info & similar tracks, save to DB"

    def add_arguments(self, parser):
        parser.add_argument("--artist", required=True, help="Artist name")
        parser.add_argument("--track", help="Seed track name (optional)")
        parser.add_argument("--chart", action="store_true", help="Import global top chart")

    def handle(self, *args, **opts):
        if opts["chart"]:
            self.import_chart()
            return

        artist_name = opts["artist"]
        self.stdout.write(f"Fetching artist {artist_name}")
        a_data = call_lastfm({"method": "artist.getInfo", "artist": artist_name, "lang": "ja"})["artist"]

        artist, _ = Artist.objects.update_or_create(
            name=a_data["name"],
            defaults={
                "mbid": a_data.get("mbid") or None,
                "url": a_data["url"],
                "listeners": a_data["stats"]["listeners"],
                "playcount": a_data["stats"]["playcount"],
                "summary": a_data["bio"]["summary"],
            },
        )

        # 類似トラック取得（seed: track param or artist top track）
        seed_track = opts.get("track") or a_data.get("name")    # fallback
        if seed_track:
            t_data = call_lastfm({
                "method": "track.getSimilar",
                "artist": artist_name,
                "track": seed_track,
                "limit": 20,
            })["similartracks"]["track"]

            for t in t_data:
                Track.objects.update_or_create(
                    title=t["name"],
                    artist=Artist.objects.get_or_create(name=t["artist"]["name"])[0],
                    defaults={
                        "url": t["url"],
                        "match": float(t["match"]),
                    },
                )
        self.stdout.write(self.style.SUCCESS("Import finished."))

    def import_chart(self):
        self.stdout.write("Fetching global top chart")
        top = call_lastfm({"method": "chart.getTopTracks", "limit": 50})["tracks"]["track"]
        for t in top:
            artist, _ = Artist.objects.get_or_create(
                name=t["artist"]["name"],
                defaults={"url": t["artist"]["url"]},
            )
            Track.objects.update_or_create(
                title=t["name"], artist=artist,
                defaults={
                    "url": t["url"],
                    "playcount": int(t["playcount"]),
                },
            )
        self.stdout.write(self.style.SUCCESS("Chart import finished."))
