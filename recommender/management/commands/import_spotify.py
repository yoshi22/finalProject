# -*- coding: utf-8 -*-
import json, time, spotipy
from django.core.management.base import BaseCommand
from recommender.spotify import get_user_client_cli
from recommender.models import Artist, Track

# ── 日本向け公式プレイリスト（ID は固定） ───────────
PLAYLISTS = {
    "Top 50 – Japan":      "37i9dQZEVXbKXQ4mDTEBXq",
    "Hot Hits Japan":      "37i9dQZF1DXaLoJqzbwXaX",   
    "Tokyo Super Hits!":   "37i9dQZF1DX7GUbsmx52wp",
    "Anime Now":           "37i9dQZF1DXd9K2N4jiwKy",
    "Dance Pop: Japan":    "37i9dQZF1DX4ORXMG8F5PN",
}


PAGE_LIMIT = 100
SLEEP_SEC  = 0.4          # API レートリミット緩和

class Command(BaseCommand):
    help = "Fetch JP‑playable Spotify tracks and store metadata + audio features"

    # ── 1. プレイリストから JP 再生可能トラックを収集 ─────────
    def _track_ids(self, sp, pids, country):
        ids = set()
        for pid in pids:
            offset = 0
            while True:
                try:
                    chunk = sp.playlist_tracks(
                        pid,
                        limit=PAGE_LIMIT,
                        offset=offset,
                        market=country
                    )
                except spotipy.SpotifyException as e:
                    if e.http_status == 404:
                        self.stderr.write(f"⚠  skip playlist {pid}: 404 not found")
                        break
                    raise  # それ以外は問題を表面化
                for item in chunk["items"]:
                    t = item.get("track") or {}
                    if t.get("id") and (t.get("is_playable") is not False):
                        mkts = t.get("available_markets", [])
                        if (not mkts) or (country in mkts):
                            ids.add(t["id"])
                if chunk["next"]:
                    offset += PAGE_LIMIT
                    time.sleep(SLEEP_SEC)
                else:
                    break
        self.stdout.write(f"✔ collected {len(ids)} JP‑playable IDs")
        return list(ids)

    # ── 2. Audio Features を 403 安全化して取得 ───────────────
    def _features_safe(self, sp, batch):
        try:
            return sp.audio_features(batch)
        except spotipy.SpotifyException as e:
            if e.http_status != 403:
                raise
            good = []
            for tid in batch:
                try:
                    good.append(sp.audio_features([tid])[0])
                except spotipy.SpotifyException:
                    good.append(None)
                    self.stderr.write(f"⚠  skip non‑playable id {tid}")
                time.sleep(0.1)
            return good

    # ── 3. DB へ保存 ──────────────────────────────────────────
    def _persist(self, sp, ids):
        for i in range(0, len(ids), 50):
            batch = ids[i:i+50]
            metas = sp.tracks(batch)["tracks"]
            feats = self._features_safe(sp, batch)

            for meta, feat in zip(metas, feats):
                if not meta or not feat:
                    continue
                art = meta["artists"][0]
                artist, _ = Artist.objects.get_or_create(
                    spotify_id=art["id"],
                    defaults={
                        "name": art["name"],
                        "genres_json": json.dumps(
                            sp.artist(art["id"]).get("genres", [])
                        ),
                    },
                )
                Track.objects.update_or_create(
                    spotify_id=meta["id"],
                    defaults=dict(
                        title      = meta["name"],
                        artist     = artist,
                        popularity = meta["popularity"],
                        features   = json.dumps([
                            feat["danceability"], feat["energy"], feat["valence"],
                            feat["acousticness"], feat["instrumentalness"],
                            feat["liveness"],     feat["speechiness"], feat["tempo"],
                        ]),
                    ),
                )
            time.sleep(SLEEP_SEC)

    # ── 4. コマンド実行 ──────────────────────────────────────
    def handle(self, *args, **opts):
        sp = get_user_client_cli()                  # 認可 (scope=user-read-private)
        country = (sp.current_user().get("country") or "JP")
        self.stdout.write(f"▶  token country: {country}")

        pids = list(PLAYLISTS.values())
        tids = self._track_ids(sp, pids, country)
        self._persist(sp, tids)

        saved = Track.objects.exclude(features="").count()
        self.stdout.write(self.style.SUCCESS(f"✅  Import finished ({saved} tracks saved)"))
