# recommender/management/commands/import_spotify.py
import json, time, spotipy
from django.core.management.base import BaseCommand
from recommender.spotify import get_user_client_cli
from recommender.models import Artist, Track

PLAYLIST_NAMES = [
    "Top 50 – Japan",
    "Hot Hits Japan",
    "Tokyo Super Hits!",
    "Anime Now",
    "Dance Pop: Japan",
]

PAGE_LIMIT = 100
SLEEP_SEC  = 0.4

class Command(BaseCommand):
    help = "Import JP‑playable tracks (≈1 000) into DB"

    # ── 0. 検索して ID を取得 ─────────────────────────────────
    def _resolve_ids(self, sp):
        ids = {}
        for name in PLAYLIST_NAMES:
            res = sp.search(f'playlist:"{name}"', type="playlist",
                            limit=1, market="JP")["playlists"]["items"]
            if res:
                ids[name] = res[0]["id"]
                self.stdout.write(f"✔ resolved '{name}' → {ids[name]}")
            else:
                self.stderr.write(f"⚠  '{name}' not found, skipped")
        return ids

    # ── 1. JP 再生可能 track_id を収集 ───────────────────────
    def _track_ids(self, sp, pid_map):
        ids = set()
        for name, pid in pid_map.items():
            offset = 0
            while True:
                try:
                    chunk = sp.playlist_tracks(pid, limit=PAGE_LIMIT,
                                               offset=offset, market="JP")
                except spotipy.SpotifyException as e:
                    if e.http_status == 404:
                        self.stderr.write(f"⚠  skip playlist {name}: 404")
                        break
                    raise
                for it in chunk["items"]:
                    t = (it or {}).get("track") or {}
                    if not t.get("id"):
                        continue
                    if t.get("is_playable") is False:
                        continue
                    mkts = t.get("available_markets", [])
                    if (not mkts) or ("JP" in mkts):
                        ids.add(t["id"])
                if chunk["next"]:
                    offset += PAGE_LIMIT
                    time.sleep(SLEEP_SEC)
                else:
                    break
        self.stdout.write(f"✔ collected {len(ids)} JP‑playable IDs")
        return list(ids)

    # ── 2. audio_features を 403 セーフで取得 ────────────────
    def _features_safe(self, sp, batch):
        try:
            return sp.audio_features(batch)
        except spotipy.SpotifyException as e:
            if e.http_status != 403:
                raise
            out = []
            for tid in batch:
                try:
                    out.append(sp.audio_features([tid])[0])
                except spotipy.SpotifyException:
                    out.append(None)
                    self.stderr.write(f"⚠  no features for {tid}")
                time.sleep(0.1)
            return out

    # ── 3. DB 保存 ───────────────────────────────────────────
    def _persist(self, sp, tids):
        for i in range(0, len(tids), 50):
            batch = tids[i:i+50]
            metas = sp.tracks(batch, market="JP")["tracks"]
            feats = self._features_safe(sp, batch)

            for meta, feat in zip(metas, feats):
                if not meta:
                    continue
                art_raw = meta["artists"][0]
                artist, _ = Artist.objects.get_or_create(
                    spotify_id=art_raw["id"],
                    defaults={
                        "name": art_raw["name"],
                        "genres_json": json.dumps(
                            sp.artist(art_raw["id"]).get("genres", [])
                        ),
                    },
                )
                Track.objects.update_or_create(
                    spotify_id=meta["id"],
                    defaults=dict(
                        title      = meta["name"],
                        artist     = artist,
                        popularity = meta["popularity"],
                        features   = json.dumps(
                            [
                                feat["danceability"],
                                feat["energy"],
                                feat["valence"],
                                feat["acousticness"],
                                feat["instrumentalness"],
                                feat["liveness"],
                                feat["speechiness"],
                                feat["tempo"],
                            ] if feat else []      # 取れない曲は空配列
                        ),
                    ),
                )
            time.sleep(SLEEP_SEC)

    # ── 4. entry point ─────────────────────────────────────
    def handle(self, *args, **opts):
        sp = get_user_client_cli()
        pid_map = self._resolve_ids(sp)
        tids    = self._track_ids(sp, pid_map)
        self._persist(sp, tids)

        self.stdout.write(self.style.SUCCESS(
            f"✅  Import finished ({Track.objects.count()} tracks saved)"
        ))
