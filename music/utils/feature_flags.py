from django.conf import settings
from django.core.cache import cache
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger("music")


class FeatureFlags:
    """Simple feature flag management system."""
    
    # Default feature flags
    DEFAULT_FLAGS = {
        "content_based_filtering": False,
        "hybrid_recommendations": False,
        "deep_cut_discovery": False,
        "collaborative_filtering": False,
        "ab_testing": False,
        "similarity_caching": True,
        "api_rate_limiting": True,
        "performance_monitoring": True,
    }
    
    @classmethod
    def is_enabled(cls, feature_name: str, user_id: Optional[int] = None) -> bool:
        """
        Check if a feature is enabled.
        
        Args:
            feature_name: Name of the feature flag
            user_id: Optional user ID for user-specific feature flags
            
        Returns:
            Boolean indicating if feature is enabled
        """
        # Check environment variable override first
        env_key = f"FEATURE_{feature_name.upper()}"
        env_value = settings.__dict__.get(env_key)
        if env_value is not None:
            return str(env_value).lower() in ("true", "1", "yes")
        
        # Check cache for dynamic flags
        cache_key = f"feature:{feature_name}"
        if user_id:
            cache_key = f"{cache_key}:{user_id}"
        
        cached_value = cache.get(cache_key)
        if cached_value is not None:
            return cached_value
        
        # Return default value
        return cls.DEFAULT_FLAGS.get(feature_name, False)
    
    @classmethod
    def set_flag(cls, feature_name: str, enabled: bool, user_id: Optional[int] = None):
        """
        Set a feature flag value.
        
        Args:
            feature_name: Name of the feature flag
            enabled: Whether to enable or disable the feature
            user_id: Optional user ID for user-specific feature flags
        """
        cache_key = f"feature:{feature_name}"
        if user_id:
            cache_key = f"{cache_key}:{user_id}"
        
        cache.set(cache_key, enabled, timeout=86400)  # 24 hours
        
        logger.info(
            f"Feature flag updated: {feature_name} = {enabled} "
            f"(user: {user_id or 'all'})"
        )
    
    @classmethod
    def get_all_flags(cls, user_id: Optional[int] = None) -> Dict[str, bool]:
        """
        Get all feature flags and their current values.
        
        Args:
            user_id: Optional user ID for user-specific feature flags
            
        Returns:
            Dictionary of feature names and their enabled status
        """
        result = {}
        for feature_name in cls.DEFAULT_FLAGS.keys():
            result[feature_name] = cls.is_enabled(feature_name, user_id)
        return result
    
    @classmethod
    def enable_content_based(cls):
        """Enable all content-based filtering features."""
        cls.set_flag("content_based_filtering", True)
        cls.set_flag("similarity_caching", True)
        logger.info("Content-based features enabled")
    
    @classmethod
    def enable_hybrid(cls):
        """Enable all hybrid recommendation features."""
        cls.enable_content_based()  # Hybrid depends on content-based
        cls.set_flag("hybrid_recommendations", True)
        cls.set_flag("collaborative_filtering", True)
        cls.set_flag("ab_testing", True)
        logger.info("Hybrid features enabled")
    
    @classmethod
    def enable_deep_cut(cls):
        """Enable all deep-cut discovery features."""
        cls.enable_hybrid()  # Deep-cut depends on hybrid
        cls.set_flag("deep_cut_discovery", True)
        logger.info("Deep-cut features enabled")


def feature_required(feature_name: str):
    """
    Decorator to check if a feature is enabled before executing a function.
    
    Args:
        feature_name: Name of the required feature flag
    """
    def decorator(func):
        def wrapper(request, *args, **kwargs):
            user_id = request.user.id if request.user.is_authenticated else None
            if not FeatureFlags.is_enabled(feature_name, user_id):
                logger.warning(
                    f"Feature {feature_name} is not enabled for user {user_id}"
                )
                from django.http import JsonResponse
                return JsonResponse(
                    {"error": f"Feature {feature_name} is not enabled"},
                    status=403
                )
            return func(request, *args, **kwargs)
        return wrapper
    return decorator