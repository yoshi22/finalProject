from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.contrib.auth import get_user_model
from .models import Track, Artist
import json

User = get_user_model()


class SimpleTrackFeatures(models.Model):
    """
    Simplified track features for content-based filtering.
    Stores normalized features and tags for similarity computation.
    """
    track = models.OneToOneField(
        Track, 
        on_delete=models.CASCADE, 
        related_name='simple_features'
    )
    
    # Normalized audio features (0.0 to 1.0)
    energy = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Energy level (0=low, 1=high)"
    )
    valence = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Musical positiveness (0=sad, 1=happy)"
    )
    tempo_normalized = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Normalized tempo (0=slow, 1=fast)"
    )
    danceability = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="How suitable for dancing"
    )
    acousticness = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Confidence of acoustic nature"
    )
    
    # Tag-based features (JSON array)
    genre_tags = models.JSONField(
        default=list,
        help_text="List of genre tags from Last.fm"
    )
    mood_tags = models.JSONField(
        default=list,
        help_text="List of mood/style tags"
    )
    
    # Popularity features
    popularity_score = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Normalized popularity (0=unknown, 1=very popular)"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_calculated = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        indexes = [
            models.Index(fields=['energy', 'valence']),
            models.Index(fields=['tempo_normalized']),
            models.Index(fields=['popularity_score']),
        ]
        verbose_name = "Simple Track Feature"
        verbose_name_plural = "Simple Track Features"
    
    def __str__(self):
        return f"Features for {self.track.name}"
    
    def get_feature_vector(self):
        """Return numerical feature vector for similarity calculation."""
        return [
            self.energy,
            self.valence,
            self.tempo_normalized,
            self.danceability,
            self.acousticness,
            self.popularity_score
        ]
    
    def get_all_tags(self):
        """Return combined list of all tags."""
        return list(set(self.genre_tags + self.mood_tags))


class TrackSimilarity(models.Model):
    """
    Pre-calculated similarity scores between tracks.
    Used for caching similarity results.
    """
    track_a = models.ForeignKey(
        Track,
        on_delete=models.CASCADE,
        related_name='similarities_as_a'
    )
    track_b = models.ForeignKey(
        Track,
        on_delete=models.CASCADE,
        related_name='similarities_as_b'
    )
    
    # Similarity scores
    cosine_similarity = models.FloatField(
        validators=[MinValueValidator(-1.0), MaxValueValidator(1.0)],
        help_text="Cosine similarity of feature vectors"
    )
    tag_similarity = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Jaccard similarity of tags"
    )
    combined_similarity = models.FloatField(
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="Weighted combination of all similarities"
    )
    
    # Metadata
    calculated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = [['track_a', 'track_b']]
        indexes = [
            models.Index(fields=['track_a', 'combined_similarity']),
            models.Index(fields=['track_b', 'combined_similarity']),
        ]
        verbose_name = "Track Similarity"
        verbose_name_plural = "Track Similarities"
    
    def __str__(self):
        return f"{self.track_a.name} ↔ {self.track_b.name}: {self.combined_similarity:.2f}"


class UserPreferences(models.Model):
    """
    User's music preferences for personalized recommendations.
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='music_preferences'
    )
    
    # Feature preferences (learned from listening history)
    preferred_energy = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    preferred_valence = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    preferred_tempo = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    preferred_danceability = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    preferred_acousticness = models.FloatField(
        default=0.5,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)]
    )
    
    # Tag preferences
    favorite_genres = models.JSONField(
        default=list,
        help_text="User's favorite genre tags"
    )
    favorite_moods = models.JSONField(
        default=list,
        help_text="User's favorite mood tags"
    )
    
    # Exploration preference
    exploration_level = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0.0), MaxValueValidator(1.0)],
        help_text="How much to explore (0=safe, 1=adventurous)"
    )
    
    # Metadata
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "User Preference"
        verbose_name_plural = "User Preferences"
    
    def __str__(self):
        return f"Preferences for {self.user.username}"
    
    def get_preference_vector(self):
        """Return user's preference as feature vector."""
        return [
            self.preferred_energy,
            self.preferred_valence,
            self.preferred_tempo,
            self.preferred_danceability,
            self.preferred_acousticness,
            0.5  # Neutral popularity preference
        ]


class UserRecommendationPreferences(models.Model):
    """
    User-specific recommendation settings
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='recommendation_preferences'
    )
    
    # Recommendation algorithm weights (0-1)
    content_weight = models.FloatField(
        default=0.4,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Content-based filtering weight"
    )
    collaborative_weight = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Collaborative filtering weight"
    )
    popularity_weight = models.FloatField(
        default=0.2,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Popularity-based weight"
    )
    trending_weight = models.FloatField(
        default=0.1,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Trending tracks weight"
    )
    
    # Diversity settings
    diversity_factor = models.FloatField(
        default=0.3,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Diversity importance (0=similar, 1=diverse)"
    )
    
    # Exploration settings
    exploration_level = models.FloatField(
        default=0.2,
        validators=[MinValueValidator(0), MaxValueValidator(1)],
        help_text="Exploration vs exploitation trade-off"
    )
    
    # A/B test group
    ab_test_group = models.CharField(
        max_length=20,
        null=True,
        blank=True,
        help_text="A/B test group assignment"
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'music_user_preferences'
        verbose_name = 'User Recommendation Preference'
        verbose_name_plural = 'User Recommendation Preferences'
    
    def normalize_weights(self):
        """
        Normalize weights (so that the sum becomes 1)
        """
        total = (
            self.content_weight + 
            self.collaborative_weight + 
            self.popularity_weight + 
            self.trending_weight
        )
        
        if total > 0:
            self.content_weight /= total
            self.collaborative_weight /= total
            self.popularity_weight /= total
            self.trending_weight /= total
    
    def save(self, *args, **kwargs):
        self.normalize_weights()
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Preferences for {self.user.username}"


class RecommendationLog(models.Model):
    """
    Log of recommendations made to users for analysis.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recommendation_logs'
    )
    seed_track = models.ForeignKey(
        Track,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='seed_for_recommendations'
    )
    recommended_tracks = models.ManyToManyField(
        Track,
        related_name='recommended_in_logs'
    )
    
    # Recommendation metadata
    method = models.CharField(
        max_length=50,
        choices=[
            ('content_based', 'Content-Based'),
            ('collaborative', 'Collaborative'),
            ('hybrid', 'Hybrid'),
            ('popularity', 'Popularity-Based'),
        ]
    )
    similarity_threshold = models.FloatField(default=0.5)
    exploration_level = models.FloatField(default=0.3)
    
    # User feedback
    tracks_played = models.ManyToManyField(
        Track,
        related_name='played_from_recommendations',
        blank=True
    )
    tracks_skipped = models.ManyToManyField(
        Track,
        related_name='skipped_from_recommendations',
        blank=True
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['user', '-created_at']),
            models.Index(fields=['method', '-created_at']),
        ]
        verbose_name = "Recommendation Log"
        verbose_name_plural = "Recommendation Logs"
    
    def __str__(self):
        return f"Recommendations for {self.user.username} at {self.created_at}"
    
    def get_effectiveness_score(self):
        """Calculate how effective this recommendation was."""
        total = self.recommended_tracks.count()
        if total == 0:
            return 0.0
        played = self.tracks_played.count()
        skipped = self.tracks_skipped.count()
        
        # Simple effectiveness: played / (played + skipped)
        if played + skipped == 0:
            return None  # No feedback yet
        return played / (played + skipped)