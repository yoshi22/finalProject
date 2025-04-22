import json, numpy as np
from sklearn.neighbors import NearestNeighbors
from django.conf import settings
from django.core.cache import cache
from recommender.models import Track, Artist, Listen   # Listen は後述

# ───────────────────────────────────────────────
def _load_feature_matrix():
    """全トラックの (n, 8) 行列と id リストを返す (キャッシュ 1h)"""
    cached = cache.get("feature_matrix")
    if cached:
        return cached
    qs = Track.objects.only("spotify_id", "features")
    ids, matrix = [], []
    for t in qs:
        vec = json.loads(t.features)
        if len(vec) == 8:          # guard
            ids.append(t.spotify_id)
            matrix.append(vec)
    X = np.asarray(matrix, dtype=np.float32)
    cache.set("feature_matrix", (ids, X), 3600)
    return ids, X

# ───────────────────────────────────────────────
def _fit_model():
    ids, X = _load_feature_matrix()
    mod  = NearestNeighbors(metric="cosine", algorithm="auto")
    mod.fit(X)
    return ids, X, mod

# ───────────────────────────────────────────────
def similar_tracks(track_id: str, k: int = 10) -> list[Track]:
    """
    指定 track_id に似た楽曲 k 件を返す（本人は除外）
    """
    ids, X, nn = cache.get_or_set("nn_model", _fit_model, 3600)
    try:
        idx = ids.index(track_id)
    except ValueError:
        return []
    dists, inds = nn.kneighbors([X[idx]], n_neighbors=k + 1)
    sim_ids = [ids[i] for i in inds[0] if ids[i] != track_id][:k]
    return list(Track.objects.filter(spotify_id__in=sim_ids))

# ───────────────────────────────────────────────
def personalized(user, k: int = 20) -> list[Track]:
    """
    ユーザーの再生履歴×コンテンツ類似で k 曲を推薦
    """
    listens = (Listen.objects
                     .filter(user=user)
                     .order_by("-played_at")
                     .values_list("track__spotify_id", flat=True)[:50])
    recs = []
    for tid in listens:
        recs.extend(similar_tracks(tid, 5))
    recs = {t.spotify_id: t for t in recs}.values()      # 重複排除
    recs = [t for t in recs if t.spotify_id not in listens]
    return recs[:k]
