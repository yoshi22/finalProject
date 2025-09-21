"""
Enhanced Deep-cut Discovery Engine
Advanced music discovery with exploration levels
"""

from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum
import numpy as np
from django.db.models import Q, F
from music.models import Track, Artist
from music.models_recommendation import SimpleTrackFeatures
from music.services.similarity_engine import SimilarityEngine
import logging

logger = logging.getLogger(__name__)


class ExplorationLevel(Enum):
    """探索レベル定義"""
    SAFE = 0.0          # 安全（人気のある似た曲）
    CONSERVATIVE = 0.25  # 保守的
    BALANCED = 0.5      # バランス
    ADVENTUROUS = 0.75  # 冒険的
    EXTREME = 1.0       # 極端（最も不人気な曲）


@dataclass
class DeepCutCandidate:
    """Deep-cut候補トラック"""
    track: Track
    similarity_score: float
    popularity_score: float
    novelty_score: float
    overall_score: float
    explanation_factors: Dict


class EnhancedDeepCutEngine:
    """
    強化されたDeep-cut推薦エンジン
    探索レベルに応じて安全な選択から極端な発見まで制御可能
    """
    
    def __init__(self):
        self.similarity_engine = SimilarityEngine()
        
        # 人気度の閾値（プレイカウント）
        self.popularity_thresholds = {
            ExplorationLevel.SAFE: 50000,
            ExplorationLevel.CONSERVATIVE: 20000,
            ExplorationLevel.BALANCED: 10000,
            ExplorationLevel.ADVENTUROUS: 5000,
            ExplorationLevel.EXTREME: 1000
        }
    
    def find_deepcuts(
        self,
        seed_track: Track,
        exploration_level: float = 0.5,
        limit: int = 15,
        min_similarity: float = 0.3,
        genre_constraint: bool = True
    ) -> List[DeepCutCandidate]:
        """
        Deep-cutトラックを発見
        
        Args:
            seed_track: シードトラック
            exploration_level: 探索レベル（0-1）
            limit: 返す曲数
            min_similarity: 最小類似度閾値
            genre_constraint: ジャンル制約を適用するか
        
        Returns:
            DeepCutCandidateのリスト
        """
        try:
            # 探索レベルから人気度閾値を計算
            max_popularity = self._calculate_popularity_threshold(exploration_level)
            
            # 候補トラックを取得
            candidates = self._get_candidate_tracks(
                seed_track,
                max_popularity,
                genre_constraint
            )
            
            if not candidates:
                logger.warning(f"No candidate tracks found for seed {seed_track.id}")
                return []
            
            # スコアリング
            scored_candidates = []
            for candidate_track in candidates[:100]:  # 計算量制限
                try:
                    candidate = self._score_candidate(
                        seed_track,
                        candidate_track,
                        exploration_level
                    )
                    
                    if candidate.similarity_score >= min_similarity:
                        scored_candidates.append(candidate)
                except Exception as e:
                    logger.error(f"Error scoring candidate {candidate_track.id}: {e}")
                    continue
            
            if not scored_candidates:
                logger.warning("No candidates passed similarity threshold")
                return []
            
            # 総合スコアでソート
            scored_candidates.sort(key=lambda x: x.overall_score, reverse=True)
            
            # 多様性を考慮した選択
            final_candidates = self._select_diverse_deepcuts(
                scored_candidates,
                limit
            )
            
            logger.info(f"Found {len(final_candidates)} deep-cuts for seed {seed_track.id}")
            return final_candidates
            
        except Exception as e:
            logger.error(f"Error in find_deepcuts: {e}")
            return []
    
    def _calculate_popularity_threshold(self, exploration_level: float) -> int:
        """
        探索レベルから人気度閾値を計算
        """
        # 線形補間で閾値を計算
        if exploration_level <= 0:
            return 100000  # 非常に人気
        elif exploration_level >= 1:
            return 500  # ほぼ無名
        else:
            # 対数スケールで補間
            max_pop = np.log10(100000)
            min_pop = np.log10(500)
            threshold = max_pop - (max_pop - min_pop) * exploration_level
            return int(10 ** threshold)
    
    def _get_candidate_tracks(
        self,
        seed_track: Track,
        max_popularity: int,
        genre_constraint: bool
    ) -> List[Track]:
        """
        候補トラックを取得
        """
        query = Track.objects.filter(
            playcount__lte=max_popularity,
            playcount__gt=0
        ).exclude(
            id=seed_track.id
        ).exclude(
            artist=seed_track.artist  # 同じアーティストは除外
        )
        
        # ジャンル制約（特徴量がある場合）
        if genre_constraint:
            try:
                seed_features = SimpleTrackFeatures.objects.get(track=seed_track)
                seed_genres = self._extract_genres(seed_features)
                if seed_genres:
                    # ジャンルタグを持つトラックをフィルタ
                    genre_q = Q()
                    for genre in seed_genres:
                        genre_q |= Q(simpletrackfeatures__genre_tags__contains=genre)
                    query = query.filter(genre_q)
            except SimpleTrackFeatures.DoesNotExist:
                pass
        
        # ランダムサンプリングして返す
        return list(query.order_by('?').select_related('artist')[:200])
    
    def _score_candidate(
        self,
        seed_track: Track,
        candidate_track: Track,
        exploration_level: float
    ) -> DeepCutCandidate:
        """
        候補トラックをスコアリング
        """
        # 類似度スコア
        similarity_score = self._calculate_similarity(seed_track, candidate_track)
        
        # 人気度スコア（低いほど良い）
        max_playcount = 100000
        popularity_score = 1 - min(1.0, candidate_track.playcount / max_playcount)
        
        # 新規性スコア
        novelty_score = self._calculate_novelty(candidate_track)
        
        # 総合スコア計算（探索レベルで重み調整）
        similarity_weight = 1 - exploration_level * 0.5  # 0.5-1.0
        novelty_weight = exploration_level  # 0-1
        popularity_weight = exploration_level * 0.5  # 0-0.5
        
        # 重みの正規化
        total_weight = similarity_weight + novelty_weight + popularity_weight
        if total_weight > 0:
            similarity_weight /= total_weight
            novelty_weight /= total_weight
            popularity_weight /= total_weight
        else:
            similarity_weight = novelty_weight = popularity_weight = 1/3
        
        overall_score = (
            similarity_score * similarity_weight +
            novelty_score * novelty_weight +
            popularity_score * popularity_weight
        )
        
        # 説明用ファクター記録
        explanation_factors = {
            'similarity': similarity_score,
            'popularity': popularity_score,
            'novelty': novelty_score,
            'weights': {
                'similarity': similarity_weight,
                'novelty': novelty_weight,
                'popularity': popularity_weight
            }
        }
        
        return DeepCutCandidate(
            track=candidate_track,
            similarity_score=similarity_score,
            popularity_score=popularity_score,
            novelty_score=novelty_score,
            overall_score=overall_score,
            explanation_factors=explanation_factors
        )
    
    def _calculate_similarity(
        self,
        track1: Track,
        track2: Track
    ) -> float:
        """
        トラック間の類似度計算
        """
        try:
            # SimilarityEngineのcalculate_track_similarityメソッドを使用
            # Trackオブジェクトを直接渡す
            similarity = self.similarity_engine.calculate_track_similarity(
                track1,
                track2
            )
            # Noneの場合はデフォルト値を返す
            return similarity if similarity is not None else 0.3
        except Exception as e:
            logger.error(f"Error calculating similarity between tracks {track1.id} and {track2.id}: {e}")
            # エラー時のデフォルト値
            return 0.3
    
    def _calculate_novelty(self, track: Track) -> float:
        """
        新規性スコアを計算
        """
        novelty = 0.5  # ベーススコア
        
        # アーティストの知名度から計算
        if track.artist and track.artist.playcount:
            artist_popularity = min(1.0, track.artist.playcount / 1000000)
            novelty *= (1 - artist_popularity * 0.5)
        
        # ユニークなタグを持つ場合ボーナス
        try:
            features = SimpleTrackFeatures.objects.get(track=track)
            unique_tags = self._count_unique_tags(features)
            if unique_tags > 3:
                novelty *= 1.2
        except SimpleTrackFeatures.DoesNotExist:
            pass
        
        return min(1.0, novelty)
    
    def _extract_genres(self, features: SimpleTrackFeatures) -> List[str]:
        """
        特徴量からジャンルを抽出
        """
        genres = []
        if features.genre_tags:
            for tag in features.genre_tags:
                if isinstance(tag, dict):
                    genres.append(tag.get('name', ''))
                elif isinstance(tag, str):
                    genres.append(tag)
        return genres
    
    def _count_unique_tags(self, features: SimpleTrackFeatures) -> int:
        """
        ユニークなタグ数をカウント
        """
        all_tags = set()
        
        if features.genre_tags:
            for tag in features.genre_tags:
                if isinstance(tag, dict):
                    all_tags.add(tag.get('name', ''))
                elif isinstance(tag, str):
                    all_tags.add(tag)
                    
        if features.mood_tags:
            for tag in features.mood_tags:
                if isinstance(tag, dict):
                    all_tags.add(tag.get('name', ''))
                elif isinstance(tag, str):
                    all_tags.add(tag)
                    
        return len(all_tags)
    
    def _select_diverse_deepcuts(
        self,
        candidates: List[DeepCutCandidate],
        limit: int
    ) -> List[DeepCutCandidate]:
        """
        多様性を考慮してDeep-cutを選択（MMRアルゴリズム）
        """
        if not candidates:
            return []
        
        selected = [candidates[0]]  # 最高スコアを選択
        remaining = candidates[1:]
        
        while len(selected) < limit and remaining:
            best_candidate = None
            best_diversity_score = -1
            
            for candidate in remaining:
                # 選択済みとの最小類似度
                min_similarity = 1.0
                for selected_candidate in selected:
                    similarity = self._calculate_similarity(
                        candidate.track,
                        selected_candidate.track
                    )
                    min_similarity = min(min_similarity, similarity)
                
                # 多様性を考慮したスコア（MMR）
                diversity_adjusted_score = (
                    candidate.overall_score * 0.7 +
                    (1 - min_similarity) * 0.3
                )
                
                if diversity_adjusted_score > best_diversity_score:
                    best_diversity_score = diversity_adjusted_score
                    best_candidate = candidate
            
            if best_candidate:
                selected.append(best_candidate)
                remaining.remove(best_candidate)
            else:
                break
        
        return selected
    
    def get_exploration_description(self, level: float) -> str:
        """
        探索レベルの説明を取得
        """
        descriptions = {
            0.0: "Playing it safe with popular, well-known tracks similar to your seed",
            0.3: "Mostly familiar territory with some lesser-known gems",
            0.5: "Balanced mix of familiar and undiscovered tracks",
            0.7: "Venturing into rarely heard territory",
            1.0: "Maximum exploration: the deepest cuts and most obscure tracks"
        }
        
        # 最も近い説明を返す
        closest = min(descriptions.keys(), key=lambda x: abs(x - level))
        return descriptions[closest]