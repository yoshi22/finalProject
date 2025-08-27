import time
import logging
from functools import wraps
from typing import Callable, Any
from django.core.cache import cache
from django.conf import settings

logger = logging.getLogger("music")


class PerformanceMonitor:
    """Performance monitoring utilities for tracking method execution times."""
    
    @staticmethod
    def track_execution_time(func: Callable) -> Callable:
        """Decorator to track and log function execution time."""
        @wraps(func)
        def wrapper(*args, **kwargs) -> Any:
            start_time = time.time()
            result = func(*args, **kwargs)
            execution_time = time.time() - start_time
            
            logger.info(
                f"{func.__module__}.{func.__name__} executed in {execution_time:.3f}s"
            )
            
            # Store metrics in cache for dashboard
            metric_key = f"perf:{func.__module__}.{func.__name__}"
            cache.set(metric_key, execution_time, timeout=3600)  # 1 hour
            
            return result
        return wrapper
    
    @staticmethod
    def track_api_call(api_name: str, endpoint: str) -> Callable:
        """Decorator to track external API calls."""
        def decorator(func: Callable) -> Callable:
            @wraps(func)
            def wrapper(*args, **kwargs) -> Any:
                start_time = time.time()
                success = False
                error_msg = None
                
                try:
                    result = func(*args, **kwargs)
                    success = True
                    return result
                except Exception as e:
                    error_msg = str(e)
                    logger.error(f"API call failed: {api_name}:{endpoint} - {error_msg}")
                    raise
                finally:
                    execution_time = time.time() - start_time
                    
                    # Log API call details
                    logger.info(
                        f"API Call: {api_name}:{endpoint} | "
                        f"Time: {execution_time:.3f}s | "
                        f"Success: {success}"
                    )
                    
                    # Track API metrics
                    metric_key = f"api:{api_name}:{endpoint}"
                    cache.set(
                        metric_key,
                        {
                            "execution_time": execution_time,
                            "success": success,
                            "error": error_msg,
                        },
                        timeout=3600,
                    )
                    
            return wrapper
        return decorator


class RecommendationMetrics:
    """Track recommendation system performance metrics."""
    
    @staticmethod
    def log_recommendation(user_id: int, track_ids: list, method: str, execution_time: float):
        """Log recommendation generation metrics."""
        logger.info(
            f"Recommendation generated | User: {user_id} | "
            f"Method: {method} | Tracks: {len(track_ids)} | "
            f"Time: {execution_time:.3f}s"
        )
        
        # Store in cache for analytics
        metric_key = f"rec:{user_id}:{method}"
        cache.set(
            metric_key,
            {
                "track_count": len(track_ids),
                "execution_time": execution_time,
                "method": method,
            },
            timeout=86400,  # 24 hours
        )
    
    @staticmethod
    def log_similarity_computation(track_id: str, similar_count: int, execution_time: float):
        """Log similarity computation metrics."""
        logger.debug(
            f"Similarity computed | Track: {track_id} | "
            f"Similar tracks: {similar_count} | Time: {execution_time:.3f}s"
        )
    
    @staticmethod
    def log_cache_hit(cache_key: str, hit: bool):
        """Log cache hit/miss events."""
        status = "HIT" if hit else "MISS"
        logger.debug(f"Cache {status}: {cache_key}")
        
        # Track cache hit rate
        metric_key = f"cache:hitrate:{cache_key.split(':')[0]}"
        current = cache.get(metric_key, {"hits": 0, "misses": 0})
        if hit:
            current["hits"] += 1
        else:
            current["misses"] += 1
        cache.set(metric_key, current, timeout=3600)


class ErrorTracker:
    """Track and categorize errors for monitoring."""
    
    @staticmethod
    def log_error(error_type: str, error_msg: str, context: dict = None):
        """Log error with context for analysis."""
        logger.error(
            f"Error Type: {error_type} | Message: {error_msg} | "
            f"Context: {context or {}}"
        )
        
        # Store error metrics
        metric_key = f"error:{error_type}"
        current = cache.get(metric_key, [])
        current.append({
            "message": error_msg,
            "context": context,
            "timestamp": time.time(),
        })
        # Keep last 100 errors
        cache.set(metric_key, current[-100:], timeout=86400)
    
    @staticmethod
    def log_api_rate_limit(api_name: str, retry_after: int = None):
        """Log API rate limit events."""
        logger.warning(
            f"API rate limit hit: {api_name} | "
            f"Retry after: {retry_after}s"
        )
        
        metric_key = f"ratelimit:{api_name}"
        cache.set(metric_key, {
            "timestamp": time.time(),
            "retry_after": retry_after,
        }, timeout=retry_after or 600)