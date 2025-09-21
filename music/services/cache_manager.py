import hashlib
import json
from typing import Any, Optional, List, Dict
from django.core.cache import cache
from django.conf import settings
import logging

from music.utils.monitoring import RecommendationMetrics

logger = logging.getLogger("music")


class CacheManager:
    """Centralized cache management for recommendation system."""
    
    # Cache key prefixes
    PREFIXES = {
        'track_features': 'features:track:',
        'similar_tracks': 'similar:tracks:',
        'user_preferences': 'prefs:user:',
        'recommendations': 'recs:user:',
        'tags': 'tags:',
        'api_response': 'api:',
    }
    
    # Cache timeout periods (in seconds)
    TIMEOUTS = {
        'track_features': 86400,      # 24 hours
        'similar_tracks': 3600,       # 1 hour
        'user_preferences': 7200,     # 2 hours
        'recommendations': 1800,      # 30 minutes
        'tags': 86400,                # 24 hours
        'api_response': 300,          # 5 minutes
    }
    
    @staticmethod
    def generate_cache_key(prefix: str, *args) -> str:
        """
        Generate a cache key from prefix and arguments.
        
        Args:
            prefix: Cache key prefix
            *args: Variable arguments to include in key
            
        Returns:
            Generated cache key
        """
        # Join arguments and create hash for long keys
        key_parts = [str(arg) for arg in args]
        key_suffix = ':'.join(key_parts)
        
        # If key is too long, hash it
        if len(key_suffix) > 200:
            key_suffix = hashlib.md5(key_suffix.encode()).hexdigest()
        
        return f"{prefix}{key_suffix}"
    
    @staticmethod
    def get(key: str, default: Any = None) -> Any:
        """
        Get value from cache.
        
        Args:
            key: Cache key
            default: Default value if not found
            
        Returns:
            Cached value or default
        """
        try:
            value = cache.get(key, default)
            is_hit = value != default
            RecommendationMetrics.log_cache_hit(key, is_hit)
            return value
        except Exception as e:
            logger.error(f"Cache get error for key {key}: {e}")
            return default
    
    @staticmethod
    def set(key: str, value: Any, timeout: Optional[int] = None):
        """
        Set value in cache.
        
        Args:
            key: Cache key
            value: Value to cache
            timeout: Cache timeout in seconds
        """
        try:
            cache.set(key, value, timeout)
            logger.debug(f"Cache set: {key} (timeout: {timeout}s)")
        except Exception as e:
            logger.error(f"Cache set error for key {key}: {e}")
    
    @staticmethod
    def delete(key: str):
        """Delete value from cache."""
        try:
            cache.delete(key)
            logger.debug(f"Cache delete: {key}")
        except Exception as e:
            logger.error(f"Cache delete error for key {key}: {e}")
    
    @staticmethod
    def delete_pattern(pattern: str):
        """
        Delete all keys matching a pattern.
        
        Args:
            pattern: Pattern to match (e.g., "similar:tracks:*")
        """
        try:
            cache.delete_pattern(pattern)
            logger.debug(f"Cache delete pattern: {pattern}")
        except Exception as e:
            logger.error(f"Cache delete pattern error for {pattern}: {e}")
    
    @staticmethod
    def get_or_set(key: str, callable_func, timeout: Optional[int] = None) -> Any:
        """
        Get from cache or compute and set if not exists.
        
        Args:
            key: Cache key
            callable_func: Function to call if cache miss
            timeout: Cache timeout in seconds
            
        Returns:
            Cached or computed value
        """
        value = CacheManager.get(key)
        
        if value is None:
            value = callable_func()
            if value is not None:
                CacheManager.set(key, value, timeout)
        
        return value


class RecommendationCache:
    """Specialized cache for recommendation results."""
    
    @staticmethod
    def cache_similar_tracks(track_id: str, 
                           similar_tracks: List,
                           params: Dict[str, Any]):
        """
        Cache similar tracks result.
        
        Args:
            track_id: ID of seed track
            similar_tracks: List of similar tracks
            params: Parameters used for similarity search
        """
        # Create cache key including parameters
        cache_key = CacheManager.generate_cache_key(
            CacheManager.PREFIXES['similar_tracks'],
            track_id,
            json.dumps(params, sort_keys=True)
        )
        
        timeout = CacheManager.TIMEOUTS['similar_tracks']
        CacheManager.set(cache_key, similar_tracks, timeout)
    
    @staticmethod
    def get_similar_tracks(track_id: str, params: Dict[str, Any]) -> Optional[List]:
        """
        Get cached similar tracks.
        
        Args:
            track_id: ID of seed track
            params: Parameters for similarity search
            
        Returns:
            Cached similar tracks or None
        """
        cache_key = CacheManager.generate_cache_key(
            CacheManager.PREFIXES['similar_tracks'],
            track_id,
            json.dumps(params, sort_keys=True)
        )
        
        return CacheManager.get(cache_key)
    
    @staticmethod
    def cache_user_recommendations(user_id: int,
                                  recommendations: List,
                                  method: str):
        """
        Cache user recommendations.
        
        Args:
            user_id: User ID
            recommendations: List of recommended tracks
            method: Recommendation method used
        """
        cache_key = CacheManager.generate_cache_key(
            CacheManager.PREFIXES['recommendations'],
            user_id,
            method
        )
        
        timeout = CacheManager.TIMEOUTS['recommendations']
        CacheManager.set(cache_key, recommendations, timeout)
    
    @staticmethod
    def get_user_recommendations(user_id: int, method: str) -> Optional[List]:
        """
        Get cached user recommendations.
        
        Args:
            user_id: User ID
            method: Recommendation method
            
        Returns:
            Cached recommendations or None
        """
        cache_key = CacheManager.generate_cache_key(
            CacheManager.PREFIXES['recommendations'],
            user_id,
            method
        )
        
        return CacheManager.get(cache_key)
    
    @staticmethod
    def invalidate_user_cache(user_id: int):
        """
        Invalidate all cache entries for a user.
        
        Args:
            user_id: User ID
        """
        # Invalidate recommendations
        pattern = f"{CacheManager.PREFIXES['recommendations']}{user_id}:*"
        CacheManager.delete_pattern(pattern)
        
        # Invalidate preferences
        pattern = f"{CacheManager.PREFIXES['user_preferences']}{user_id}:*"
        CacheManager.delete_pattern(pattern)
        
        logger.info(f"Invalidated cache for user {user_id}")
    
    @staticmethod
    def invalidate_track_cache(track_id: str):
        """
        Invalidate all cache entries for a track.
        
        Args:
            track_id: Track ID
        """
        # Invalidate features
        key = f"{CacheManager.PREFIXES['track_features']}{track_id}"
        CacheManager.delete(key)
        
        # Invalidate similar tracks
        pattern = f"{CacheManager.PREFIXES['similar_tracks']}{track_id}:*"
        CacheManager.delete_pattern(pattern)
        
        logger.info(f"Invalidated cache for track {track_id}")


class CacheWarmer:
    """Pre-populate cache with frequently accessed data."""
    
    @staticmethod
    def warm_popular_tracks(limit: int = 100):
        """
        Pre-cache data for popular tracks.
        
        Args:
            limit: Number of popular tracks to cache
        """
        from music.models import Track
        from music.services.similarity_engine import SimilarityEngine
        
        logger.info(f"Starting cache warming for top {limit} tracks")
        
        # Get most popular tracks
        popular_tracks = Track.objects.filter(
            simple_features__isnull=False
        ).order_by('-popularity')[:limit]
        
        warmed_count = 0
        
        for track in popular_tracks:
            try:
                # Find and cache similar tracks
                similar = SimilarityEngine.find_similar_tracks(track, limit=20)
                
                if similar:
                    warmed_count += 1
                    
            except Exception as e:
                logger.error(f"Error warming cache for track {track.id}: {e}")
        
        logger.info(f"Cache warming complete: {warmed_count} tracks processed")
        return warmed_count
    
    @staticmethod
    def warm_user_preferences(user_ids: List[int]):
        """
        Pre-cache user preferences.
        
        Args:
            user_ids: List of user IDs to cache
        """
        from music.models_recommendation import UserPreferences
        
        logger.info(f"Warming cache for {len(user_ids)} users")
        
        warmed_count = 0
        
        for user_id in user_ids:
            try:
                # Get user preferences
                prefs = UserPreferences.objects.get(user_id=user_id)
                
                # Cache the preferences
                cache_key = CacheManager.generate_cache_key(
                    CacheManager.PREFIXES['user_preferences'],
                    user_id
                )
                
                CacheManager.set(
                    cache_key,
                    prefs.get_preference_vector(),
                    CacheManager.TIMEOUTS['user_preferences']
                )
                
                warmed_count += 1
                
            except UserPreferences.DoesNotExist:
                logger.debug(f"No preferences for user {user_id}")
            except Exception as e:
                logger.error(f"Error warming cache for user {user_id}: {e}")
        
        logger.info(f"User preference cache warming complete: {warmed_count} users")
        return warmed_count