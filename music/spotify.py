# music/spotify.py
"""
Light-weight Spotify helper
───────────────────────────
・client-credentials flow
・audio_features を 100 件まとめ取りしてキーを判定
・audio_analysis は audio_features が取れない ID だけフォールバック
・Django cache（なければローカル dict）で結果を保存
"""
from __future__ import annotations
import os, time, logging
from typing import Final, Optional, Tuple, Dict, Any, List

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# ─── 認証情報 ─────────────────────────────────────────────────────────
CID: Final[str] = os.getenv("SPOTIFY_CLIENT_ID", "")
SECRET: Final[str] = os.getenv("SPOTIFY_CLIENT_SECRET", "")

if not CID or not SECRET:
    logging.warning("SPOTIFY_CLIENT_ID / SECRET が未設定。Spotify 連携は無効。")

# ─── キャッシュ（Django がなければフォールバック） ────────────────
try:
    from django.core.cache import cache as _cache  # type: ignore
except ModuleNotFoundError:
    _local: Dict[str, Tuple[Any, float]] = {}

    class _Dummy:
        def get(self, k):                      # noqa: D401
            v = _local.get(k)
            if not v:
                return None
            val, exp = v
            if exp < time.time():
                _local.pop(k, None)
                return None
            return val

        def set(self, k, v, ttl):              # noqa: D401
            _local[k] = (v, time.time() + ttl)

    _cache = _Dummy()                          # type: ignore
cache = _cache                                  # alias

# ─── Spotipy クライアント ────────────────────────────────────────────
_sp: Optional[spotipy.Spotify] = None
_token_exp: float = 0.0


def _client() -> spotipy.Spotify:
    global _sp, _token_exp                      # noqa: PLW0603
    if _sp and _token_exp - time.time() > 30:
        return _sp

    auth = SpotifyClientCredentials(client_id=CID, client_secret=SECRET)
    try:
        tk = auth.get_access_token(as_dict=True)
        token, _token_exp = tk["access_token"], tk["expires_at"]
    except TypeError:                           # Spotipy < 2.25
        token, _token_exp = auth.get_access_token(), time.time() + 3600

    _sp = spotipy.Spotify(auth=token, requests_timeout=5, retries=2)
    return _sp


# ─── 内部 util ───────────────────────────────────────────────────────
def _midi_range_from_key(key: int) -> Optional[Tuple[int, int]]:
    if key == -1:                               # key=-1 は不明
        return None
    base = 60 + key            # C4(60) を中心にシフト
    return base - 6, base + 6  # ±1 octave の半分＝±6 半音


# ─── Public: track 検索 ───────────────────────────────────────────────
def spotify_id(artist: str, title: str) -> Optional[str]:
    if not CID or not SECRET:
        return None
    try:
        items = _client().search(
            f"track:{title} artist:{artist}", type="track", limit=1
        )["tracks"]["items"]
        return items[0]["id"] if items else None
    except Exception as exc:                    # noqa: BLE001
        logging.warning("Spotify search error: %s", exc)
        return None


# ─── Public: pitch_range (単体) ───────────────────────────────────────
def pitch_range(
    track_id: str,
    *,
    use_cache: bool = True,
    cache_ttl: int = 60 * 60 * 24,
) -> Optional[Tuple[int, int]]:
    """1 曲だけ必要な場合のラッパー。"""
    return pitch_ranges_bulk([track_id], use_cache=use_cache, cache_ttl=cache_ttl)[
        track_id
    ]


# ─── Public: pitch_range (まとめ取り) ────────────────────────────────
def pitch_ranges_bulk(
    track_ids: List[str],
    *,
    use_cache: bool = True,
    cache_ttl: int = 60 * 60 * 24,
) -> Dict[str, Optional[Tuple[int, int]]]:
    """
    複数 ID のキーを **最小 1 API コール** で取得する。
    403/404 や key=-1 は None をキャッシュして踏み直さない。
    """
    if not CID or not SECRET or not track_ids:
        return {tid: None for tid in track_ids}

    results: Dict[str, Optional[Tuple[int, int]]] = {}

    # -------- 1) キャッシュ hit チェック --------------------------------
    pending: List[str] = []
    if use_cache:
        for tid in track_ids:
            cached = cache.get(f"pitch_range:{tid}")
            if cached is not None:
                results[tid] = cached          # None も含む
            else:
                pending.append(tid)
    else:
        pending = track_ids[:]

    # -------- 2) audio_features を 100 件ずつまとめて呼び出し -----------
    for chunk in [pending[i : i + 100] for i in range(0, len(pending), 100)]:
        try:
            feats = _client().audio_features(chunk)
        except spotipy.SpotifyException as exc:
            logging.warning("audio_features %s: %s", exc.http_status, exc)
            feats = [None] * len(chunk)
        except Exception as exc:               # noqa: BLE001
            logging.warning("audio_features error: %s", exc)
            feats = [None] * len(chunk)

        # audio_features が取れた ID はここで完結
        unresolved: List[str] = []
        for tid, feat in zip(chunk, feats):
            rng = _midi_range_from_key(feat["key"]) if feat else None
            if rng or feat is None:           # 成功 or 403/404
                results[tid] = rng
                if use_cache:
                    cache.set(f"pitch_range:{tid}", rng, cache_ttl)
            else:                             # 何らかの理由で key が取れない
                unresolved.append(tid)

        # -------- 3) 残った ID だけ audio_analysis でフォールバック ------
        for tid in unresolved:
            try:
                ana = _client().audio_analysis(tid)
                rng = _midi_range_from_key(ana["track"]["key"])
            except spotipy.SpotifyException as exc:
                if exc.http_status == 401:    # token 失効 → 1 回だけ再試行
                    global _sp                # noqa: PLW0603
                    _sp = None
                    try:
                        ana = _client().audio_analysis(tid)
                        rng = _midi_range_from_key(ana["track"]["key"])
                    except Exception:         # noqa: BLE001
                        rng = None
                else:
                    logging.warning("audio_analysis %s: %s", exc.http_status, exc)
                    rng = None
            except Exception as exc:          # noqa: BLE001
                logging.warning("audio_analysis error: %s", exc)
                rng = None

            results[tid] = rng
            if use_cache:
                cache.set(f"pitch_range:{tid}", rng, cache_ttl)

    return results
