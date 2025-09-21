from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from django.shortcuts import get_object_or_404
import logging
import time

from music.models import Track
from music.models_recommendation import SimpleTrackFeatures, UserPreferences, RecommendationLog
from music.services.similarity_engine import SimilarityEngine, DiversityOptimizer
from music.services.feature_extraction import FeatureExtractor
from music.services.cache_manager import RecommendationCache
from music.utils.feature_flags import FeatureFlags, feature_required
from music.utils.monitoring import RecommendationMetrics
from music.api.serializers import (
    TrackSerializer,
    SimpleTrackFeaturesSerializer,
    RecommendationRequestSerializer,
    SimilarTrackSerializer
)

logger = logging.getLogger("music")


class SimilarTracksAPIView(APIView):
    """API endpoint for getting similar tracks based on content-based filtering."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request, track_id):
        """
        Get tracks similar to a given track.
        
        Query Parameters:
            - limit: Maximum number of results (default: 20)
            - min_similarity: Minimum similarity threshold (default: 0.5)
            - diversity: Apply diversity optimization (default: false)
            - lambda_param: MMR lambda parameter if diversity=true (default: 0.7)
        """
        if not FeatureFlags.is_enabled('content_based_filtering'):
            return Response(
                {"error": "Content-based filtering is not enabled"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        start_time = time.time()
        
        # Get track
        track = get_object_or_404(Track, id=track_id)
        
        # Parse query parameters
        limit = int(request.query_params.get('limit', 20))
        min_similarity = float(request.query_params.get('min_similarity', 0.5))
        use_diversity = request.query_params.get('diversity', 'false').lower() == 'true'
        lambda_param = float(request.query_params.get('lambda_param', 0.7))
        
        # Validate parameters
        limit = min(max(1, limit), 100)  # Between 1 and 100
        min_similarity = min(max(0.0, min_similarity), 1.0)  # Between 0 and 1
        lambda_param = min(max(0.0, lambda_param), 1.0)  # Between 0 and 1
        
        # Check cache
        cache_params = {
            'limit': limit,
            'min_similarity': min_similarity,
            'diversity': use_diversity,
            'lambda_param': lambda_param if use_diversity else None
        }
        
        cached_result = RecommendationCache.get_similar_tracks(track_id, cache_params)
        
        if cached_result:
            logger.debug(f"Cache hit for similar tracks: track_id={track_id}")
            return Response({
                'seed_track': TrackSerializer(track).data,
                'similar_tracks': cached_result,
                'parameters': cache_params,
                'cached': True
            })
        
        # Ensure track has features
        if not hasattr(track, 'simple_features'):
            # Try to extract features
            features = FeatureExtractor.extract_track_features(track)
            if not features:
                return Response(
                    {"error": "Could not extract features for this track"},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Find similar tracks
        similar_tracks = SimilarityEngine.find_similar_tracks(
            track, limit=limit*2 if use_diversity else limit, min_similarity=min_similarity
        )
        
        if not similar_tracks:
            return Response(
                {"message": "No similar tracks found"},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Apply diversity if requested
        if use_diversity:
            similar_tracks = DiversityOptimizer.apply_mmr(
                similar_tracks, lambda_param=lambda_param, num_results=limit
            )
        
        # Serialize results
        result_data = []
        for similar_track, similarity_score in similar_tracks[:limit]:
            result_data.append({
                'track': TrackSerializer(similar_track).data,
                'similarity_score': round(similarity_score, 3)
            })
        
        # Cache the result
        RecommendationCache.cache_similar_tracks(track_id, result_data, cache_params)
        
        # Log recommendation
        execution_time = time.time() - start_time
        RecommendationMetrics.log_recommendation(
            request.user.id,
            [t[0].id for t in similar_tracks[:limit]],
            'content_based',
            execution_time
        )
        
        # Create recommendation log
        if request.user.is_authenticated:
            rec_log = RecommendationLog.objects.create(
                user=request.user,
                seed_track=track,
                method='content_based',
                similarity_threshold=min_similarity,
                exploration_level=1.0 - lambda_param if use_diversity else 0.0
            )
            rec_log.recommended_tracks.set([t[0] for t in similar_tracks[:limit]])
        
        return Response({
            'seed_track': TrackSerializer(track).data,
            'similar_tracks': result_data,
            'parameters': cache_params,
            'cached': False,
            'execution_time': round(execution_time, 3)
        })


class ExtractFeaturesAPIView(APIView):
    """API endpoint for extracting features for a track."""
    
    permission_classes = [IsAuthenticated]
    
    def post(self, request, track_id):
        """
        Extract and store features for a track.
        """
        track = get_object_or_404(Track, id=track_id)
        
        # Check if features already exist
        if hasattr(track, 'simple_features'):
            return Response({
                'message': 'Features already exist',
                'features': SimpleTrackFeaturesSerializer(track.simple_features).data
            })
        
        # Extract features
        features = FeatureExtractor.extract_track_features(track)
        
        if features:
            return Response({
                'message': 'Features extracted successfully',
                'features': SimpleTrackFeaturesSerializer(features).data
            }, status=status.HTTP_201_CREATED)
        else:
            return Response(
                {'error': 'Failed to extract features'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class UserPreferencesAPIView(APIView):
    """API endpoint for managing user preferences."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """Get current user's preferences."""
        try:
            preferences = UserPreferences.objects.get(user=request.user)
            return Response({
                'preferences': {
                    'energy': preferences.preferred_energy,
                    'valence': preferences.preferred_valence,
                    'tempo': preferences.preferred_tempo,
                    'danceability': preferences.preferred_danceability,
                    'acousticness': preferences.preferred_acousticness,
                    'exploration_level': preferences.exploration_level,
                    'favorite_genres': preferences.favorite_genres,
                    'favorite_moods': preferences.favorite_moods
                }
            })
        except UserPreferences.DoesNotExist:
            # Create default preferences
            preferences = UserPreferences.objects.create(user=request.user)
            return Response({
                'message': 'Default preferences created',
                'preferences': {
                    'energy': preferences.preferred_energy,
                    'valence': preferences.preferred_valence,
                    'tempo': preferences.preferred_tempo,
                    'danceability': preferences.preferred_danceability,
                    'acousticness': preferences.preferred_acousticness,
                    'exploration_level': preferences.exploration_level,
                    'favorite_genres': [],
                    'favorite_moods': []
                }
            })
    
    def post(self, request):
        """Update user's preferences."""
        preferences, created = UserPreferences.objects.get_or_create(
            user=request.user
        )
        
        # Update preferences from request data
        data = request.data
        
        # Update audio feature preferences
        if 'energy' in data:
            preferences.preferred_energy = float(data['energy'])
        if 'valence' in data:
            preferences.preferred_valence = float(data['valence'])
        if 'tempo' in data:
            preferences.preferred_tempo = float(data['tempo'])
        if 'danceability' in data:
            preferences.preferred_danceability = float(data['danceability'])
        if 'acousticness' in data:
            preferences.preferred_acousticness = float(data['acousticness'])
        
        # Update exploration level
        if 'exploration_level' in data:
            preferences.exploration_level = float(data['exploration_level'])
        
        # Update tag preferences
        if 'favorite_genres' in data:
            preferences.favorite_genres = data['favorite_genres']
        if 'favorite_moods' in data:
            preferences.favorite_moods = data['favorite_moods']
        
        preferences.save()
        
        # Invalidate user's cache
        from music.services.cache_manager import RecommendationCache
        RecommendationCache.invalidate_user_cache(request.user.id)
        
        return Response({
            'message': 'Preferences updated successfully',
            'preferences': {
                'energy': preferences.preferred_energy,
                'valence': preferences.preferred_valence,
                'tempo': preferences.preferred_tempo,
                'danceability': preferences.preferred_danceability,
                'acousticness': preferences.preferred_acousticness,
                'exploration_level': preferences.exploration_level,
                'favorite_genres': preferences.favorite_genres,
                'favorite_moods': preferences.favorite_moods
            }
        })


class PersonalizedRecommendationsAPIView(APIView):
    """API endpoint for personalized recommendations based on user preferences."""
    
    permission_classes = [IsAuthenticated]
    
    def get(self, request):
        """
        Get personalized recommendations for the current user.
        
        Query Parameters:
            - limit: Maximum number of results (default: 20)
            - seed_track_id: Optional seed track for recommendations
            - use_preferences: Use user preferences (default: true)
        """
        if not FeatureFlags.is_enabled('content_based_filtering'):
            return Response(
                {"error": "Content-based filtering is not enabled"},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Get or create user preferences
        preferences, created = UserPreferences.objects.get_or_create(
            user=request.user
        )
        
        # Parse parameters
        limit = min(int(request.query_params.get('limit', 20)), 100)
        seed_track_id = request.query_params.get('seed_track_id')
        use_preferences = request.query_params.get('use_preferences', 'true').lower() == 'true'
        
        # Check cache
        cache_key_suffix = f"{seed_track_id}:{use_preferences}:{limit}"
        cached_result = RecommendationCache.get_user_recommendations(
            request.user.id, 
            f"personalized:{cache_key_suffix}"
        )
        
        if cached_result:
            return Response({
                'recommendations': cached_result,
                'cached': True
            })
        
        recommendations = []
        
        if seed_track_id:
            # Get seed track
            seed_track = get_object_or_404(Track, id=seed_track_id)
            
            # Find similar tracks
            similar_tracks = SimilarityEngine.find_similar_tracks(
                seed_track, 
                limit=limit * 2,
                min_similarity=0.4
            )
            
            # Apply user preferences if enabled
            if use_preferences and similar_tracks:
                # Filter based on exploration level
                exploration_level = preferences.exploration_level
                
                # Apply diversity based on exploration level
                similar_tracks = DiversityOptimizer.apply_mmr(
                    similar_tracks,
                    lambda_param=1.0 - exploration_level,
                    num_results=limit
                )
            
            recommendations = similar_tracks[:limit]
            
        else:
            # Get recommendations based on user preferences alone
            # This would require finding tracks that match user's preference vector
            # For now, return popular tracks that match preferences
            from music.models import Track
            
            tracks = Track.objects.filter(
                simple_features__isnull=False
            ).select_related('simple_features')
            
            # Score tracks based on preference match
            scored_tracks = []
            pref_vector = preferences.get_preference_vector()
            
            for track in tracks[:100]:  # Limit to 100 for performance
                if hasattr(track, 'simple_features'):
                    feature_vector = track.simple_features.get_feature_vector()
                    
                    # Calculate similarity to preferences
                    import numpy as np
                    from sklearn.metrics.pairwise import cosine_similarity
                    
                    pref_array = np.array(pref_vector).reshape(1, -1)
                    feature_array = np.array(feature_vector).reshape(1, -1)
                    
                    similarity = cosine_similarity(pref_array, feature_array)[0][0]
                    similarity = (similarity + 1) / 2  # Convert to 0-1
                    
                    scored_tracks.append((track, similarity))
            
            # Sort by score
            scored_tracks.sort(key=lambda x: x[1], reverse=True)
            recommendations = scored_tracks[:limit]
        
        # Serialize results
        result_data = []
        for track, score in recommendations:
            result_data.append({
                'track': TrackSerializer(track).data,
                'score': round(score, 3)
            })
        
        # Cache results
        RecommendationCache.cache_user_recommendations(
            request.user.id,
            result_data,
            f"personalized:{cache_key_suffix}"
        )
        
        # Log recommendation
        if recommendations:
            rec_log = RecommendationLog.objects.create(
                user=request.user,
                seed_track_id=seed_track_id if seed_track_id else None,
                method='content_based',
                exploration_level=preferences.exploration_level
            )
            rec_log.recommended_tracks.set([t[0] for t in recommendations])
        
        return Response({
            'recommendations': result_data,
            'cached': False,
            'used_preferences': use_preferences,
            'exploration_level': preferences.exploration_level
        })