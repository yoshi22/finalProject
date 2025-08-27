import numpy as np
from typing import List, Dict, Optional, Tuple
from sklearn.metrics.pairwise import cosine_similarity
from django.db import transaction
from django.core.cache import cache
import logging

from music.models import Track
from music.models_recommendation import SimpleTrackFeatures, TrackSimilarity
from music.services.feature_extraction import TagAnalyzer
from music.utils.monitoring import PerformanceMonitor, RecommendationMetrics
from music.utils.feature_flags import FeatureFlags

logger = logging.getLogger("music")


class SimilarityEngine:
    """Engine for calculating track similarities using content-based filtering."""
    
    # Weight configuration for different similarity components
    WEIGHTS = {
        'audio_features': 0.6,  # Weight for audio feature similarity
        'tags': 0.3,            # Weight for tag similarity
        'popularity': 0.1       # Weight for popularity similarity
    }
    
    @staticmethod
    @PerformanceMonitor.track_execution_time
    def calculate_track_similarity(track_a: Track, track_b: Track) -> Optional[float]:
        """
        Calculate similarity between two tracks.
        
        Args:
            track_a: First track
            track_b: Second track
            
        Returns:
            Combined similarity score (0-1) or None if calculation fails
        """
        try:
            # Get features for both tracks
            features_a = track_a.simple_features if hasattr(track_a, 'simple_features') else None
            features_b = track_b.simple_features if hasattr(track_b, 'simple_features') else None
            
            if not features_a or not features_b:
                logger.warning(f"Missing features for tracks {track_a.id} or {track_b.id}")
                return None
            
            # Calculate audio feature similarity
            audio_sim = SimilarityEngine._calculate_audio_similarity(features_a, features_b)
            
            # Calculate tag similarity
            tag_sim = SimilarityEngine._calculate_tag_similarity(features_a, features_b)
            
            # Calculate popularity similarity
            pop_sim = SimilarityEngine._calculate_popularity_similarity(features_a, features_b)
            
            # Combine similarities with weights
            combined_similarity = (
                SimilarityEngine.WEIGHTS['audio_features'] * audio_sim +
                SimilarityEngine.WEIGHTS['tags'] * tag_sim +
                SimilarityEngine.WEIGHTS['popularity'] * pop_sim
            )
            
            return combined_similarity
            
        except Exception as e:
            logger.error(f"Error calculating similarity: {e}")
            return None
    
    @staticmethod
    def _calculate_audio_similarity(features_a: SimpleTrackFeatures, 
                                   features_b: SimpleTrackFeatures) -> float:
        """Calculate cosine similarity of audio features."""
        vector_a = np.array(features_a.get_feature_vector())
        vector_b = np.array(features_b.get_feature_vector())
        
        # Reshape for sklearn
        vector_a = vector_a.reshape(1, -1)
        vector_b = vector_b.reshape(1, -1)
        
        # Calculate cosine similarity
        similarity = cosine_similarity(vector_a, vector_b)[0][0]
        
        # Convert from [-1, 1] to [0, 1]
        return (similarity + 1) / 2
    
    @staticmethod
    def _calculate_tag_similarity(features_a: SimpleTrackFeatures,
                                 features_b: SimpleTrackFeatures) -> float:
        """Calculate tag-based similarity."""
        tags_a = features_a.get_all_tags()
        tags_b = features_b.get_all_tags()
        
        # Use weighted similarity if tags have positions
        return TagAnalyzer.weighted_tag_similarity(tags_a, tags_b)
    
    @staticmethod
    def _calculate_popularity_similarity(features_a: SimpleTrackFeatures,
                                        features_b: SimpleTrackFeatures) -> float:
        """Calculate popularity-based similarity."""
        # Simple difference-based similarity
        diff = abs(features_a.popularity_score - features_b.popularity_score)
        return 1.0 - diff  # Convert difference to similarity
    
    @staticmethod
    @PerformanceMonitor.track_execution_time
    def find_similar_tracks(seed_track: Track, 
                           limit: int = 20,
                           min_similarity: float = 0.5) -> List[Tuple[Track, float]]:
        """
        Find tracks similar to a seed track.
        
        Args:
            seed_track: Track to find similarities for
            limit: Maximum number of similar tracks to return
            min_similarity: Minimum similarity threshold
            
        Returns:
            List of (track, similarity_score) tuples, sorted by similarity
        """
        # Check cache first
        cache_key = f"similar_tracks:{seed_track.id}:{limit}:{min_similarity}"
        cached_result = cache.get(cache_key)
        
        if cached_result and FeatureFlags.is_enabled('similarity_caching'):
            RecommendationMetrics.log_cache_hit(cache_key, True)
            return cached_result
        
        RecommendationMetrics.log_cache_hit(cache_key, False)
        
        # Get seed track features
        if not hasattr(seed_track, 'simple_features'):
            logger.warning(f"No features for seed track {seed_track.id}")
            return []
        
        # Check pre-calculated similarities
        similar_tracks = SimilarityEngine._get_precalculated_similarities(
            seed_track, limit, min_similarity
        )
        
        if similar_tracks:
            # Cache the result
            cache.set(cache_key, similar_tracks, timeout=3600)  # 1 hour
            return similar_tracks
        
        # Calculate similarities on the fly if not pre-calculated
        similar_tracks = SimilarityEngine._calculate_similarities_batch(
            seed_track, limit, min_similarity
        )
        
        # Cache the result
        cache.set(cache_key, similar_tracks, timeout=3600)
        
        # Log metrics
        RecommendationMetrics.log_similarity_computation(
            seed_track.id,
            len(similar_tracks),
            0.0  # Execution time tracked by decorator
        )
        
        return similar_tracks
    
    @staticmethod
    def _get_precalculated_similarities(seed_track: Track,
                                       limit: int,
                                       min_similarity: float) -> List[Tuple[Track, float]]:
        """Get pre-calculated similarities from database."""
        similarities = TrackSimilarity.objects.filter(
            track_a=seed_track,
            combined_similarity__gte=min_similarity
        ).select_related('track_b').order_by('-combined_similarity')[:limit]
        
        results = []
        for sim in similarities:
            results.append((sim.track_b, sim.combined_similarity))
        
        return results
    
    @staticmethod
    def _calculate_similarities_batch(seed_track: Track,
                                     limit: int,
                                     min_similarity: float) -> List[Tuple[Track, float]]:
        """Calculate similarities for tracks without pre-calculated values."""
        # Get all tracks with features
        all_tracks = Track.objects.filter(
            simple_features__isnull=False
        ).exclude(id=seed_track.id).select_related('simple_features')[:100]
        
        similarities = []
        
        for track in all_tracks:
            similarity = SimilarityEngine.calculate_track_similarity(seed_track, track)
            if similarity and similarity >= min_similarity:
                similarities.append((track, similarity))
        
        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:limit]
    
    @staticmethod
    @PerformanceMonitor.track_execution_time
    def precalculate_similarities(tracks: List[Track], 
                                batch_size: int = 100,
                                min_similarity: float = 0.3):
        """
        Pre-calculate and store similarities between tracks.
        
        Args:
            tracks: List of tracks to process
            batch_size: Number of comparisons per batch
            min_similarity: Minimum similarity to store
        """
        total_tracks = len(tracks)
        comparisons_made = 0
        similarities_stored = 0
        
        logger.info(f"Starting similarity pre-calculation for {total_tracks} tracks")
        
        for i in range(total_tracks):
            track_a = tracks[i]
            
            # Skip if no features
            if not hasattr(track_a, 'simple_features'):
                continue
            
            batch_similarities = []
            
            for j in range(i + 1, min(i + batch_size, total_tracks)):
                track_b = tracks[j]
                
                if not hasattr(track_b, 'simple_features'):
                    continue
                
                # Calculate similarity
                similarity = SimilarityEngine.calculate_track_similarity(track_a, track_b)
                comparisons_made += 1
                
                if similarity and similarity >= min_similarity:
                    # Prepare for bulk creation
                    audio_sim = SimilarityEngine._calculate_audio_similarity(
                        track_a.simple_features, track_b.simple_features
                    )
                    tag_sim = SimilarityEngine._calculate_tag_similarity(
                        track_a.simple_features, track_b.simple_features
                    )
                    
                    batch_similarities.append(
                        TrackSimilarity(
                            track_a=track_a,
                            track_b=track_b,
                            cosine_similarity=audio_sim * 2 - 1,  # Convert back to [-1, 1]
                            tag_similarity=tag_sim,
                            combined_similarity=similarity
                        )
                    )
            
            # Bulk create similarities
            if batch_similarities:
                with transaction.atomic():
                    TrackSimilarity.objects.bulk_create(
                        batch_similarities,
                        ignore_conflicts=True
                    )
                    similarities_stored += len(batch_similarities)
            
            if (i + 1) % 10 == 0:
                logger.info(f"Progress: {i + 1}/{total_tracks} tracks, "
                          f"{comparisons_made} comparisons, "
                          f"{similarities_stored} similarities stored")
        
        logger.info(f"Similarity pre-calculation complete: "
                   f"{comparisons_made} comparisons, "
                   f"{similarities_stored} similarities stored")
        
        return comparisons_made, similarities_stored


class DiversityOptimizer:
    """Optimize recommendation diversity using MMR (Maximal Marginal Relevance)."""
    
    @staticmethod
    def apply_mmr(similar_tracks: List[Tuple[Track, float]],
                 lambda_param: float = 0.7,
                 num_results: int = 10) -> List[Tuple[Track, float]]:
        """
        Apply Maximal Marginal Relevance to balance relevance and diversity.
        
        Args:
            similar_tracks: List of (track, similarity) tuples
            lambda_param: Balance parameter (0=diverse, 1=relevant)
            num_results: Number of results to return
            
        Returns:
            Reranked list optimizing for diversity
        """
        if not similar_tracks:
            return []
        
        # Start with the most similar track
        selected = [similar_tracks[0]]
        remaining = similar_tracks[1:]
        
        while len(selected) < num_results and remaining:
            best_score = -1
            best_idx = -1
            
            for idx, (candidate_track, candidate_sim) in enumerate(remaining):
                # Calculate relevance (similarity to seed)
                relevance = candidate_sim
                
                # Calculate diversity (min similarity to selected tracks)
                min_sim_to_selected = 1.0
                for selected_track, _ in selected:
                    sim = SimilarityEngine.calculate_track_similarity(
                        candidate_track, selected_track
                    )
                    if sim is not None:
                        min_sim_to_selected = min(min_sim_to_selected, sim)
                
                # MMR score
                mmr_score = (lambda_param * relevance + 
                           (1 - lambda_param) * (1 - min_sim_to_selected))
                
                if mmr_score > best_score:
                    best_score = mmr_score
                    best_idx = idx
            
            if best_idx >= 0:
                selected.append(remaining[best_idx])
                remaining.pop(best_idx)
            else:
                break
        
        return selected