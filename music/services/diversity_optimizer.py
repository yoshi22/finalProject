import numpy as np
from typing import List, Tuple, Set, Dict
from music.models import Track
from music.models_recommendation import SimpleTrackFeatures
import logging

logger = logging.getLogger(__name__)


class DiversityOptimizer:
    """
    推薦結果の多様性を最適化
    """
    
    def optimize(
        self,
        recommendations: List[Tuple[Track, float]],
        diversity_weight: float = 0.3,
        method: str = 'mmr'
    ) -> List[Tuple[Track, float]]:
        """
        多様性最適化を実行
        
        Args:
            recommendations: (track, score)のリスト
            diversity_weight: 多様性の重要度（0-1）
            method: 最適化手法（'mmr', 'determinantal', 'greedy'）
        
        Returns:
            最適化された推薦リスト
        """
        if method == 'mmr':
            return self._mmr_optimization(recommendations, diversity_weight)
        elif method == 'greedy':
            return self._greedy_optimization(recommendations, diversity_weight)
        else:
            return recommendations
    
    def _mmr_optimization(
        self,
        recommendations: List[Tuple[Track, float]],
        lambda_param: float
    ) -> List[Tuple[Track, float]]:
        """
        Maximal Marginal Relevance (MMR)による最適化
        """
        if not recommendations:
            return []
        
        selected = []
        candidates = recommendations.copy()
        
        # 最初のアイテムは最高スコアを選択
        first_item = max(candidates, key=lambda x: x[1])
        selected.append(first_item)
        candidates.remove(first_item)
        
        while candidates:
            best_score = -float('inf')
            best_item = None
            
            for candidate, relevance in candidates:
                # 関連性スコア
                rel_score = relevance
                
                # 多様性スコア（選択済みとの最大類似度）
                max_sim = 0
                for selected_track, _ in selected:
                    similarity = self._calculate_similarity(
                        candidate, selected_track
                    )
                    max_sim = max(max_sim, similarity)
                
                # MMRスコア
                mmr_score = (
                    lambda_param * rel_score - 
                    (1 - lambda_param) * max_sim
                )
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_item = (candidate, relevance)
            
            if best_item:
                selected.append(best_item)
                candidates.remove(best_item)
        
        return selected
    
    def _greedy_optimization(
        self,
        recommendations: List[Tuple[Track, float]],
        diversity_weight: float
    ) -> List[Tuple[Track, float]]:
        """
        貪欲法による多様性最適化
        """
        if not recommendations:
            return []
        
        selected = []
        candidates = recommendations.copy()
        
        # 最初のアイテムを選択
        selected.append(candidates.pop(0))
        
        while candidates and len(selected) < len(recommendations):
            best_score = -float('inf')
            best_idx = -1
            
            for idx, (candidate, relevance) in enumerate(candidates):
                # 多様性スコア計算
                diversity = self._calculate_diversity_to_set(
                    candidate, [s[0] for s in selected]
                )
                
                # 統合スコア
                combined_score = (
                    (1 - diversity_weight) * relevance +
                    diversity_weight * diversity
                )
                
                if combined_score > best_score:
                    best_score = combined_score
                    best_idx = idx
            
            if best_idx >= 0:
                selected.append(candidates.pop(best_idx))
        
        return selected
    
    def _calculate_similarity(
        self,
        track1: Track,
        track2: Track
    ) -> float:
        """
        トラック間の類似度計算
        """
        # アーティストが同じ場合
        if track1.artist_id == track2.artist_id:
            return 0.8
        
        # 特徴量ベースの類似度
        features1 = self._get_track_features(track1)
        features2 = self._get_track_features(track2)
        
        if features1 is not None and features2 is not None:
            # コサイン類似度計算
            similarity = self._cosine_similarity(features1, features2)
        else:
            # ジャンルの重複度
            genres1 = self._get_track_genres(track1)
            genres2 = self._get_track_genres(track2)
            
            if genres1 and genres2:
                intersection = len(genres1 & genres2)
                union = len(genres1 | genres2)
                similarity = intersection / union if union > 0 else 0
            else:
                similarity = 0.1  # デフォルト低類似度
        
        return similarity
    
    def _calculate_diversity_to_set(
        self,
        candidate: Track,
        selected: List[Track]
    ) -> float:
        """
        候補と選択済みセットとの多様性スコア
        """
        if not selected:
            return 1.0
        
        # 最小類似度を計算
        min_similarity = 1.0
        for track in selected:
            similarity = self._calculate_similarity(candidate, track)
            min_similarity = min(min_similarity, similarity)
        
        # 多様性は最小類似度の逆
        return 1 - min_similarity
    
    def _get_track_features(self, track: Track) -> np.ndarray:
        """
        トラックの特徴量ベクトルを取得
        """
        try:
            if hasattr(track, 'simple_features') and track.simple_features:
                features = track.simple_features
                return np.array([
                    features.energy,
                    features.valence,
                    features.tempo_normalized,
                    features.danceability,
                    features.acousticness,
                    features.popularity_score
                ])
        except:
            pass
        
        return None
    
    def _get_track_genres(self, track: Track) -> Set[str]:
        """
        トラックのジャンルを取得
        """
        genres = set()
        
        try:
            if hasattr(track, 'simple_features') and track.simple_features:
                genres = set(track.simple_features.genre_tags)
        except:
            pass
        
        return genres
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """
        コサイン類似度計算
        """
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)
    
    def calculate_diversity_metrics(
        self,
        recommendations: List[Track]
    ) -> Dict[str, float]:
        """
        多様性メトリクスを計算
        """
        if not recommendations:
            return {
                'intra_list_diversity': 0,
                'genre_coverage': 0,
                'artist_diversity': 0,
                'feature_diversity': 0
            }
        
        # Intra-List Diversity（ILD）
        ild = self._calculate_intra_list_diversity(recommendations)
        
        # ジャンルカバレッジ
        genre_coverage = self._calculate_genre_coverage(recommendations)
        
        # アーティスト多様性
        artist_diversity = self._calculate_artist_diversity(recommendations)
        
        # 特徴量多様性
        feature_diversity = self._calculate_feature_diversity(recommendations)
        
        return {
            'intra_list_diversity': ild,
            'genre_coverage': genre_coverage,
            'artist_diversity': artist_diversity,
            'feature_diversity': feature_diversity
        }
    
    def _calculate_intra_list_diversity(self, recommendations: List[Track]) -> float:
        """
        Intra-List Diversity計算
        """
        if len(recommendations) < 2:
            return 0.0
        
        total_distance = 0
        count = 0
        
        for i in range(len(recommendations)):
            for j in range(i + 1, len(recommendations)):
                similarity = self._calculate_similarity(
                    recommendations[i],
                    recommendations[j]
                )
                total_distance += (1 - similarity)
                count += 1
        
        return total_distance / count if count > 0 else 0
    
    def _calculate_genre_coverage(self, recommendations: List[Track]) -> float:
        """
        ジャンルカバレッジ計算
        """
        all_genres = set()
        for track in recommendations:
            all_genres.update(self._get_track_genres(track))
        
        # 20を最大ジャンル数と仮定
        max_genres = 20
        return min(1.0, len(all_genres) / max_genres)
    
    def _calculate_artist_diversity(self, recommendations: List[Track]) -> float:
        """
        アーティスト多様性計算
        """
        unique_artists = len(set(t.artist_id for t in recommendations))
        return unique_artists / len(recommendations) if recommendations else 0
    
    def _calculate_feature_diversity(self, recommendations: List[Track]) -> float:
        """
        特徴量の多様性計算
        """
        if len(recommendations) < 2:
            return 0.0
        
        features_list = []
        for track in recommendations:
            features = self._get_track_features(track)
            if features is not None:
                features_list.append(features)
        
        if len(features_list) < 2:
            return 0.0
        
        # 特徴量の標準偏差を計算
        features_array = np.array(features_list)
        std_devs = np.std(features_array, axis=0)
        
        # 平均標準偏差を多様性スコアとして使用
        return np.mean(std_devs)
    
    def apply_mmr(
        self,
        candidates: List[Tuple[Track, float]],
        lambda_param: float = 0.7,
        num_results: int = 20
    ) -> List[Tuple[Track, float]]:
        """
        MMRアルゴリズムを適用（外部から直接呼び出し可能）
        
        Args:
            candidates: (track, score)のリスト
            lambda_param: 関連性と多様性のバランス（0-1）
            num_results: 返す結果数
        
        Returns:
            MMR最適化された推薦リスト
        """
        if not candidates:
            return []
        
        # 結果数を制限
        num_results = min(num_results, len(candidates))
        
        # MMR最適化を実行
        optimized = self._mmr_optimization(candidates, lambda_param)
        
        return optimized[:num_results]
    
    def rerank_for_diversity(
        self,
        recommendations: List[Tuple[Track, float]],
        target_diversity: float = 0.5,
        max_iterations: int = 10
    ) -> List[Tuple[Track, float]]:
        """
        目標多様性に到達するまで再ランキング
        
        Args:
            recommendations: 初期推薦リスト
            target_diversity: 目標多様性スコア
            max_iterations: 最大反復回数
        
        Returns:
            多様性最適化された推薦リスト
        """
        current_recs = recommendations
        current_diversity = 0.0
        
        for iteration in range(max_iterations):
            # 現在の多様性を計算
            tracks = [r[0] for r in current_recs]
            metrics = self.calculate_diversity_metrics(tracks)
            current_diversity = metrics['intra_list_diversity']
            
            # 目標に到達したら終了
            if current_diversity >= target_diversity:
                logger.info(f"Target diversity reached in {iteration} iterations")
                break
            
            # λパラメータを調整してMMRを再実行
            lambda_param = max(0.1, 1.0 - (iteration + 1) * 0.1)
            current_recs = self._mmr_optimization(current_recs, lambda_param)
        
        return current_recs