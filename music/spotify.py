"""
Light-weight Spotify helper
───────────────────────────
・client-credentials flow（Spotipy）
・audio_features を 50 件ずつまとめ取得して key→歌唱レンジ判定
・audio_analysis は key==-1／features 取得失敗分のみフォールバック
・Django cache（なければローカル dict）で結果を保存
"""
from __future__ import annotations

import logging
import os
import time
from typing import Any, Dict, Final, List, Optional, Tuple

import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

# ────────────────────────────────────────────────────────────────────
# 認証情報
# ────────────────────────────────────────────────────────────────────
CID: Final[str] = os.getenv("SPOTIFY_CLIENT_ID", "")
SECRET: Final[str] = os.getenv("SPOTIFY_CLIENT_SECRET", "")

if not CID or not SECRET:
    logging.warning("SPOTIFY_CLIENT_ID / SECRET が未設定。Spotify 連携は無効です。")

# ────────────────────────────────────────────────────────────────────
# キャッシュ（Django が無い環境ではフォールバック実装）
# ────────────────────────────────────────────────────────────────────
try:
    from django.core.cache import cache as _cache  # type: ignore
except ModuleNotFoundError:
    _local: Dict[str, Tuple[Any, float]] = {}

    class _DummyCache:  # pylint: disable=too-few-public-methods
        def get(self, key: str) -> Any:  # noqa: D401
            val = _local.get(key)
            if not val:
                return None
            data, exp = val
            if exp < time.time():
                _local.pop(key, None)
                return None
            return data

        def set(self, key: str, val: Any, ttl: int) -> None:  # noqa: D401
            _local[key] = (val, time.time() + ttl)

    _cache = _DummyCache()  # type: ignore

cache = _cache  # alias 統一

# ────────────────────────────────────────────────────────────────────
# Spotipy クライアントを “プロセス内で” 共有
# ────────────────────────────────────────────────────────────────────
_sp: Optional[spotipy.Spotify] = None
_token_exp: float = 0.0  # epoch seconds


def _client() -> spotipy.Spotify:
    """
    Spotipy インスタンスをキャッシュ付きで返す。
    トークン残り 30 秒を切ったら再取得。
    """
    global _sp, _token_exp  # noqa: PLW0603

    if _sp and _token_exp - time.time() > 30:
        return _sp

    auth = SpotifyClientCredentials(client_id=CID, client_secret=SECRET)
    try:  # Spotipy ≥ 2.25
        tk = auth.get_access_token(as_dict=True)
        token, _token_exp = tk["access_token"], tk["expires_at"]
    except TypeError:  # Spotipy < 2.25
        token, _token_exp = auth.get_access_token(), time.time() + 3600

    _sp = spotipy.Spotify(auth=token, requests_timeout=5, retries=2)
    return _sp


# ────────────────────────────────────────────────────────────────────
# 内部 util
# ────────────────────────────────────────────────────────────────────
def _midi_range_from_key(key: int) -> Optional[Tuple[int, int]]:
    """Spotify key(0=C) → (low, high) を返す。取れなければ None"""
    if key == -1:
        return None
    center = 60 + key          # C4(60) を基準にシフト
    return center - 6, center + 6


def _chunk(lst: List[str], size: int = 50):
    """[abcde] → [[a…size], …]"""
    for i in range(0, len(lst), size):
        yield lst[i : i + size]


# ────────────────────────────────────────────────────────────────────
# Public: Spotify track を検索し ID を返す
# ────────────────────────────────────────────────────────────────────
def spotify_id(artist: str, title: str) -> Optional[str]:
    if not CID or not SECRET:
        return None
    try:
        res = _client().search(
            f"track:{title} artist:{artist}", type="track", limit=1
        )
        items = res["tracks"]["items"]
        return items[0]["id"] if items else None
    except Exception as exc:  # noqa: BLE001
        logging.warning("Spotify search error: %s", exc)
        return None


# ────────────────────────────────────────────────────────────────────
# Public: 単体 pitch_range
# ────────────────────────────────────────────────────────────────────
def pitch_range(
    track_id: str,
    *,
    use_cache: bool = True,
    cache_ttl: int = 60 * 60 * 24,
) -> Optional[Tuple[int, int]]:
    """1 曲だけ欲しい場合の軽量ラッパー"""
    return pitch_ranges_bulk([track_id], use_cache=use_cache, cache_ttl=cache_ttl)[
        track_id
    ]


# ────────────────────────────────────────────────────────────────────
# Public: 複数曲まとめて pitch_range
# ────────────────────────────────────────────────────────────────────
def pitch_ranges_bulk(
    track_ids: List[str],
    *,
    use_cache: bool = True,
    cache_ttl: int = 60 * 60 * 24,
) -> Dict[str, Optional[Tuple[int, int]]]:
    """
    可能な限り **少ない API コール** で歌唱レンジを取得する。

    1. まず audio_features を ≤50 件ずつまとめ取得
    2. key==-1 / features が取れなかった ID だけ audio_analysis でフォールバック
    3. 403 / 404 や key==-1 は None をキャッシュ → 次回即 return None
    """
    if not CID or not SECRET or not track_ids:
        return {tid: None for tid in track_ids}

    results: Dict[str, Optional[Tuple[int, int]]] = {}

    # ――― 1) キャッシュ先取り ―――
    pending: List[str] = []
    if use_cache:
        for tid in track_ids:
            if (val := cache.get(f"pitch_range:{tid}")) is not None:
                results[tid] = val  # None もここに入る
            else:
                pending.append(tid)
    else:
        pending = track_ids[:]

    # ――― 2) audio_features 一括取得 ―――
    for chunk in _chunk(pending, 50):  # 50 件ずつ ⇒ 403 を回避しやすい
        try:
            feats = _client().audio_features(chunk) or []
        except spotipy.SpotifyException as exc:
            logging.warning("audio_features %s: %s", exc.http_status, exc)
            feats = [None] * len(chunk)
        except Exception as exc:  # noqa: BLE001
            logging.warning("audio_features error: %s", exc)
            feats = [None] * len(chunk)

        # features が取れた ID はここで終了
        unresolved: List[str] = []
        for tid, feat in zip(chunk, feats):
            rng = _midi_range_from_key(feat["key"]) if feat else None
            if rng is not None or feat is None:
                results[tid] = rng
                if use_cache:
                    cache.set(f"pitch_range:{tid}", rng, cache_ttl)
            else:  # feat はあるが key==-1
                unresolved.append(tid)

        # ――― 3) audio_analysis フォールバック ―――
        for tid in unresolved:
            try:
                ana = _client().audio_analysis(tid)
                rng = _midi_range_from_key(ana["track"]["key"])
            except spotipy.SpotifyException as exc:
                if exc.http_status == 401:
                    # token 失効 → 1 回だけ再取得
                    global _sp  # noqa: PLW0603
                    _sp = None
                    try:
                        ana = _client().audio_analysis(tid)
                        rng = _midi_range_from_key(ana["track"]["key"])
                    except Exception:  # noqa: BLE001
                        rng = None
                else:
                    logging.warning("audio_analysis %s: %s", exc.http_status, exc)
                    rng = None
            except Exception as exc:  # noqa: BLE001
                logging.warning("audio_analysis error: %s", exc)
                rng = None

            results[tid] = rng
            if use_cache:
                cache.set(f"pitch_range:{tid}", rng, cache_ttl)

    return results
