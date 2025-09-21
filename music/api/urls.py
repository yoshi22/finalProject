from django.urls import path
from music.api.views import (
    SimilarTracksAPIView,
    ExtractFeaturesAPIView,
    UserPreferencesAPIView,
    PersonalizedRecommendationsAPIView
)
from music.api.feedback import (
    submit_feedback,
    get_exploration_profile,
    reset_exploration_profile,
    get_feedback_history
)

app_name = 'music_api'

urlpatterns = [
    # Content-based filtering endpoints
    path('tracks/<str:track_id>/similar/', 
         SimilarTracksAPIView.as_view(), 
         name='similar-tracks'),
    
    path('tracks/<str:track_id>/extract-features/', 
         ExtractFeaturesAPIView.as_view(), 
         name='extract-features'),
    
    # User preference endpoints
    path('preferences/', 
         UserPreferencesAPIView.as_view(), 
         name='user-preferences'),
    
    # Personalized recommendations
    path('recommendations/personalized/', 
         PersonalizedRecommendationsAPIView.as_view(), 
         name='personalized-recommendations'),
    
    # Feedback endpoints
    path('feedback/', 
         submit_feedback, 
         name='submit-feedback'),
    
    path('feedback/history/', 
         get_feedback_history, 
         name='feedback-history'),
    
    path('profile/exploration/', 
         get_exploration_profile, 
         name='exploration-profile'),
    
    path('profile/exploration/reset/', 
         reset_exploration_profile, 
         name='reset-exploration-profile'),
]