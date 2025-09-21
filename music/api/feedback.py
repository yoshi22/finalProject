"""
Feedback API endpoints
Collect and process user feedback for recommendations
"""

from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from music.models import Track, RecommendationFeedback, UserExplorationProfile
import logging

logger = logging.getLogger(__name__)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def submit_feedback(request):
    """
    Submit recommendation feedback
    
    POST /api/v1/feedback/
    {
        "track_id": 123,
        "seed_track_id": 456,
        "feedback_type": "like",
        "feedback_value": 1.0,
        "exploration_level": 0.5,
        "recommendation_score": 0.8,
        "position": 3,
        "session_id": "abc123"
    }
    """
    user = request.user
    data = request.data
    
    # Validate required fields
    if 'track_id' not in data or 'feedback_type' not in data:
        return Response(
            {"error": "track_id and feedback_type are required"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Validate feedback type
    valid_types = ['like', 'dislike', 'save', 'skip', 'play', 'play_full']
    if data['feedback_type'] not in valid_types:
        return Response(
            {"error": f"Invalid feedback_type. Must be one of {valid_types}"},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        with transaction.atomic():
            # Track validation
            track = Track.objects.get(id=data['track_id'])
            seed_track = None
            if 'seed_track_id' in data:
                try:
                    seed_track = Track.objects.get(id=data['seed_track_id'])
                except Track.DoesNotExist:
                    logger.warning(f"Seed track {data['seed_track_id']} not found")
            
            # Create or update feedback
            feedback_data = {
                'feedback_type': data['feedback_type'],
                'feedback_value': data.get('feedback_value', 1.0),
                'exploration_level': data.get('exploration_level'),
                'recommendation_score': data.get('recommendation_score'),
                'position_in_list': data.get('position')
            }
            
            # Maintain uniqueness if session ID exists
            if data.get('session_id'):
                feedback, created = RecommendationFeedback.objects.update_or_create(
                    user=user,
                    track=track,
                    seed_track=seed_track,
                    session_id=data['session_id'],
                    defaults=feedback_data
                )
            else:
                # Create new if no session ID
                feedback = RecommendationFeedback.objects.create(
                    user=user,
                    track=track,
                    seed_track=seed_track,
                    **feedback_data
                )
                created = True
            
            # Update user profile
            profile, _ = UserExplorationProfile.objects.get_or_create(user=user)
            profile.update_from_feedback(feedback)
            
            logger.info(f"Feedback {'created' if created else 'updated'} for user {user.id}, track {track.id}")
            
            return Response(
                {
                    "status": "success",
                    "created": created,
                    "feedback_id": feedback.id
                },
                status=status.HTTP_201_CREATED if created else status.HTTP_200_OK
            )
            
    except Track.DoesNotExist:
        return Response(
            {"error": "Invalid track ID"},
            status=status.HTTP_400_BAD_REQUEST
        )
    except Exception as e:
        logger.error(f"Error submitting feedback: {e}")
        return Response(
            {"error": "Failed to submit feedback"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_exploration_profile(request):
    """
    Get user exploration profile
    
    GET /api/v1/profile/exploration/
    """
    user = request.user
    
    try:
        profile = UserExplorationProfile.objects.get(user=user)
        data = {
            'preferred_exploration_level': profile.preferred_exploration_level,
            'novelty_tolerance': profile.novelty_tolerance,
            'genre_flexibility': profile.genre_flexibility,
            'deepcut_acceptance_rate': profile.deepcut_acceptance_rate,
            'total_feedbacks': profile.total_feedbacks,
            'positive_feedbacks': profile.positive_feedbacks,
            'negative_feedbacks': profile.negative_feedbacks,
            'recommendation_weights': profile.get_recommendation_weights()
        }
    except UserExplorationProfile.DoesNotExist:
        # Return default values
        data = {
            'preferred_exploration_level': 0.5,
            'novelty_tolerance': 0.5,
            'genre_flexibility': 0.5,
            'deepcut_acceptance_rate': 0.5,
            'total_feedbacks': 0,
            'positive_feedbacks': 0,
            'negative_feedbacks': 0,
            'recommendation_weights': {
                'similarity': 0.5,
                'novelty': 0.15,
                'popularity': 0.15,
                'diversity': 0.2
            }
        }
    
    return Response(data, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def reset_exploration_profile(request):
    """
    Reset exploration profile
    
    POST /api/v1/profile/exploration/reset/
    """
    user = request.user
    
    try:
        profile, created = UserExplorationProfile.objects.get_or_create(user=user)
        
        # Reset to default values
        profile.preferred_exploration_level = 0.5
        profile.novelty_tolerance = 0.5
        profile.genre_flexibility = 0.5
        profile.deepcut_acceptance_rate = 0.5
        profile.total_feedbacks = 0
        profile.positive_feedbacks = 0
        profile.negative_feedbacks = 0
        profile.save()
        
        logger.info(f"Reset exploration profile for user {user.id}")
        
        return Response(
            {"status": "success", "message": "Profile reset to default values"},
            status=status.HTTP_200_OK
        )
        
    except Exception as e:
        logger.error(f"Error resetting profile: {e}")
        return Response(
            {"error": "Failed to reset profile"},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_feedback_history(request):
    """
    Get user feedback history
    
    GET /api/v1/feedback/history/
    Query params:
        - limit: Number of items to retrieve (default: 50)
        - offset: Offset
        - feedback_type: Feedback type to filter
    """
    user = request.user
    
    # Get parameters
    limit = int(request.GET.get('limit', 50))
    offset = int(request.GET.get('offset', 0))
    feedback_type = request.GET.get('feedback_type')
    
    # Build query
    query = RecommendationFeedback.objects.filter(user=user)
    
    if feedback_type:
        query = query.filter(feedback_type=feedback_type)
    
    # Get total count
    total = query.count()
    
    # Get data
    feedbacks = query.order_by('-created_at')[offset:offset+limit]
    
    # Build response
    data = {
        'total': total,
        'limit': limit,
        'offset': offset,
        'feedbacks': [
            {
                'id': fb.id,
                'track_id': fb.track.id,
                'track_title': fb.track.title,
                'artist_name': fb.track.artist.name if fb.track.artist else None,
                'feedback_type': fb.feedback_type,
                'exploration_level': fb.exploration_level,
                'created_at': fb.created_at.isoformat()
            }
            for fb in feedbacks
        ]
    }
    
    return Response(data, status=status.HTTP_200_OK)