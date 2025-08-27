from django.urls import path
from music.api.views import (
    SimilarTracksAPIView,
    ExtractFeaturesAPIView,
    UserPreferencesAPIView,
    PersonalizedRecommendationsAPIView
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
]