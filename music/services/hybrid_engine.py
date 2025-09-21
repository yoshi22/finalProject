from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
from enum import Enum
import numpy as np
from django.db.models import Q
from music.models import Track, Artist
from music.models_recommendation import SimpleTrackFeatures
from music.services.similarity_engine import SimilarityEngine
from django.contrib.auth import get_user_model
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
User = get_user_model()


class RecommendationType(Enum):
    CONTENT_BASED = "content_based"
    COLLABORATIVE = "collaborative"
    POPULARITY = "popularity"
    TRENDING = "trending"


@dataclass
class RecommendationSource:
    """推薦ソースのメタデータ"""
    type: RecommendationType
    tracks: List[Track]
    scores: List[float]
    weight: float
    metadata: Dict = None


class HybridRecommendationEngine:
    """
    複数の推薦手法を統合するハイブリッドエンジン
    """
    
    def __init__(self):
        self.similarity_engine = SimilarityEngine()
        self.collaborative_recommender = None  # To be implemented
        self.default_weights = {
            RecommendationType.CONTENT_BASED: 0.4,
            RecommendationType.COLLABORATIVE: 0.3,
            RecommendationType.POPULARITY: 0.2,
            RecommendationType.TRENDING: 0.1
        }
    
    def recommend(
        self,
        user: User,
        seed_track: Optional[Track] = None,
        limit: int = 20,
        diversity_factor: float = 0.3,
        custom_weights: Optional[Dict] = None
    ) -> List[Tuple[Track, float, Dict]]:
        """
        Execute hybrid recommendations
        
        Args:
            user: Target user
            seed_track: Seed track (optional)
            limit: Number of recommendations to return
            diversity_factor: Diversity importance (0-1)
            custom_weights: Custom weight settings
        
        Returns:
            List of (track, score, metadata)
        """
        # 各推薦ソースから結果を取得
        sources = self._gather_recommendations(
            user, seed_track, limit * 3
        )
        
        # 重み設定
        weights = custom_weights or self._get_user_weights(user)
        
        # スコアを統合
        merged_results = self._merge_recommendations(
            sources, weights
        )
        
        # 多様性最適化
        if diversity_factor > 0:
            merged_results = self._optimize_diversity(
                merged_results, diversity_factor
            )
        
        # 上位N件を返す
        return merged_results[:limit]
    
    def _gather_recommendations(
        self,
        user: User,
        seed_track: Optional[Track],
        limit: int
    ) -> List[RecommendationSource]:
        """
        Collect results from each recommendation algorithm
        """
        sources = []
        
        # コンテンツベース推薦
        if seed_track:
            content_results = self.similarity_engine.find_similar_tracks(
                seed_track, limit=limit
            )
            if content_results:
                sources.append(RecommendationSource(
                    type=RecommendationType.CONTENT_BASED,
                    tracks=[r[0] for r in content_results],
                    scores=[r[1] for r in content_results],
                    weight=self.default_weights[RecommendationType.CONTENT_BASED]
                ))
        
        # Collaborative filtering (simple implementation)
        if self.collaborative_recommender:
            # To be implemented
            pass
        
        # 人気度ベース推薦
        popularity_results = self._get_popularity_recommendations(limit)
        if popularity_results:
            sources.append(RecommendationSource(
                type=RecommendationType.POPULARITY,
                tracks=[r[0] for r in popularity_results],
                scores=[r[1] for r in popularity_results],
                weight=self.default_weights[RecommendationType.POPULARITY]
            ))
        
        # Trending (temporal popularity)
        trending_results = self._get_trending_recommendations(limit)
        if trending_results:
            sources.append(RecommendationSource(
                type=RecommendationType.TRENDING,
                tracks=[r[0] for r in trending_results],
                scores=[r[1] for r in trending_results],
                weight=self.default_weights[RecommendationType.TRENDING]
            ))
        
        return sources
    
    def _merge_recommendations(
        self,
        sources: List[RecommendationSource],
        weights: Dict
    ) -> List[Tuple[Track, float, Dict]]:
        """
        Merge recommendations from multiple sources
        """
        # トラックごとのスコアを集計
        track_scores = {}
        track_metadata = {}
        
        for source in sources:
            source_weight = weights.get(source.type, 0.1)
            
            for track, score in zip(source.tracks, source.scores):
                if track.id not in track_scores:
                    track_scores[track.id] = 0
                    track_metadata[track.id] = {
                        'sources': [],
                        'track': track
                    }
                
                # 重み付きスコアを加算
                weighted_score = score * source_weight
                track_scores[track.id] += weighted_score
                
                # メタデータ記録
                track_metadata[track.id]['sources'].append({
                    'type': source.type.value,
                    'original_score': score,
                    'weighted_score': weighted_score
                })
        
        # スコアで降順ソート
        sorted_tracks = sorted(
            track_scores.items(),
            key=lambda x: x[1],
            reverse=True
        )
        
        # 結果を整形
        results = []
        for track_id, final_score in sorted_tracks:
            metadata = track_metadata[track_id]
            results.append((
                metadata['track'],
                final_score,
                metadata
            ))
        
        return results
    
    def _optimize_diversity(
        self,
        recommendations: List[Tuple[Track, float, Dict]],
        diversity_factor: float
    ) -> List[Tuple[Track, float, Dict]]:
        """
        Optimize diversity of recommendations
        Using MMR (Maximal Marginal Relevance) algorithm
        """
        if not recommendations:
            return []
        
        selected = []
        candidates = recommendations.copy()
        
        # 最初の1件は最高スコアを選択
        selected.append(candidates.pop(0))
        
        while candidates and len(selected) < len(recommendations):
            best_score = -1
            best_idx = -1
            
            for idx, (candidate, score, meta) in enumerate(candidates):
                # 関連性スコア
                relevance = score
                
                # 多様性スコア（選択済みとの最小類似度）
                diversity = self._calculate_diversity_score(
                    candidate, [s[0] for s in selected]
                )
                
                # MMRスコア計算
                mmr_score = (
                    (1 - diversity_factor) * relevance +
                    diversity_factor * diversity
                )
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx
            
            if best_idx >= 0:
                selected.append(candidates.pop(best_idx))
        
        return selected
    
    def _calculate_diversity_score(
        self,
        candidate: Track,
        selected: List[Track]
    ) -> float:
        """
        Calculate diversity score between candidate and selected tracks
        """
        if not selected:
            return 1.0
        
        # ジャンルの多様性
        candidate_genres = set()
        if hasattr(candidate, 'simple_features') and candidate.simple_features:
            candidate_genres = set(candidate.simple_features.genre_tags)
        
        min_similarity = 1.0
        for track in selected:
            selected_genres = set()
            if hasattr(track, 'simple_features') and track.simple_features:
                selected_genres = set(track.simple_features.genre_tags)
            
            if candidate_genres and selected_genres:
                intersection = len(candidate_genres & selected_genres)
                union = len(candidate_genres | selected_genres)
                similarity = intersection / union if union > 0 else 0
            else:
                similarity = 0.5  # デフォルト値
            
            min_similarity = min(min_similarity, similarity)
        
        return 1 - min_similarity  # 多様性は類似度の逆
    
    def _get_popularity_recommendations(
        self, 
        limit: int
    ) -> List[Tuple[Track, float]]:
        """
        Popularity-based recommendations
        """
        popular_tracks = Track.objects.filter(
            playcount__isnull=False
        ).order_by('-playcount')[:limit]
        
        results = []
        if popular_tracks:
            max_playcount = popular_tracks[0].playcount
            
            for track in popular_tracks:
                # プレイカウントを0-1に正規化
                score = track.playcount / max_playcount if max_playcount > 0 else 0
                results.append((track, score))
        
        return results
    
    def _get_trending_recommendations(
        self, 
        limit: int
    ) -> List[Tuple[Track, float]]:
        """
        Trending recommendations (recent popularity)
        Simple implementation: High playcount tracks updated recently
        """
        # 過去30日間のトラック
        recent_date = datetime.now() - timedelta(days=30)
        
        trending_tracks = Track.objects.filter(
            fetched_at__gte=recent_date,
            playcount__isnull=False
        ).order_by('-playcount')[:limit]
        
        results = []
        if trending_tracks:
            max_playcount = trending_tracks[0].playcount
            for track in trending_tracks:
                score = track.playcount / max_playcount if max_playcount > 0 else 0
                results.append((track, score))
        
        return results
    
    def _get_user_weights(self, user: User) -> Dict:
        """
        ユーザー固有の重み設定を取得
        """
        # Get weights from UserRecommendationPreferences
        if hasattr(user, 'recommendation_preferences'):
            prefs = user.recommendation_preferences
            return {
                RecommendationType.CONTENT_BASED: prefs.content_weight,
                RecommendationType.COLLABORATIVE: prefs.collaborative_weight,
                RecommendationType.POPULARITY: prefs.popularity_weight,
                RecommendationType.TRENDING: prefs.trending_weight
            }
        
        # デフォルト値を返す
        return self.default_weights