from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class Artist(models.Model):
    name = models.CharField(max_length=200, unique=True)
    mbid = models.CharField(max_length=36, blank=True, null=True)
    url = models.URLField(blank=True)
    listeners = models.PositiveIntegerField(default=0)
    playcount = models.PositiveIntegerField(default=0)
    summary = models.TextField(blank=True)
    fetched_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name


class Track(models.Model):
    title = models.CharField(max_length=200)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="tracks")
    mbid = models.CharField(max_length=36, blank=True, null=True)
    url = models.URLField(blank=True)
    playcount = models.PositiveIntegerField(default=0)
    match = models.FloatField(null=True, blank=True)
    fetched_at = models.DateTimeField(auto_now=True)
    preview_url = models.URLField(blank=True)  

    class Meta:
        unique_together = ("title", "artist")
        ordering = ["-playcount"]

    def __str__(self):
        return f"{self.title} — {self.artist.name}"
    

# ----------  User models  ------------------------------------
class VocalProfile(models.Model):
    user      = models.OneToOneField(User, on_delete=models.CASCADE)
    note_min  = models.PositiveSmallIntegerField(
        default=60, help_text="…"
    )
    note_max  = models.PositiveSmallIntegerField(
        default=72, help_text="…"
    )

    


# ----------  Playlist models  ------------------------------------
class Playlist(models.Model):
    owner = models.ForeignKey(User, on_delete=models.CASCADE, related_name="playlists")
    name = models.CharField(max_length=120)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("owner", "name")

    def __str__(self):
        return f"{self.name} ({self.owner.username})"


class PlaylistTrack(models.Model):
    playlist = models.ForeignKey(Playlist, on_delete=models.CASCADE, related_name="items")
    track = models.ForeignKey(Track, on_delete=models.CASCADE)
    position = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = ("playlist", "track")
        ordering = ["position"]

# Import recommendation models
from .models_recommendation import (
    SimpleTrackFeatures,
    TrackSimilarity,
    UserPreferences,
    RecommendationLog
)

# Feedback Models
from typing import Dict
import logging

logger = logging.getLogger(__name__)


class RecommendationFeedback(models.Model):
    """
    User feedback for recommendations
    """
    FEEDBACK_TYPES = [
        ('like', 'Like'),
        ('dislike', 'Dislike'),
        ('save', 'Save'),
        ('skip', 'Skip'),
        ('play', 'Play'),
        ('play_full', 'Play Full'),
    ]
    
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='recommendation_feedbacks'
    )
    track = models.ForeignKey(
        Track,
        on_delete=models.CASCADE,
        related_name='feedbacks'
    )
    seed_track = models.ForeignKey(
        Track,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='seed_feedbacks'
    )
    
    feedback_type = models.CharField(
        max_length=20,
        choices=FEEDBACK_TYPES
    )
    feedback_value = models.FloatField(
        default=1.0,
        help_text="Feedback strength (e.g., play duration percentage)"
    )
    
    exploration_level = models.FloatField(null=True, blank=True)
    recommendation_score = models.FloatField(null=True, blank=True)
    position_in_list = models.IntegerField(null=True, blank=True)
    
    session_id = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'music_recommendation_feedback'
        indexes = [
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['track', 'feedback_type']),
            models.Index(fields=['seed_track', 'user']),
        ]
        unique_together = [
            ('user', 'track', 'seed_track', 'session_id')
        ]
    
    def __str__(self):
        return f"{self.user.username} - {self.feedback_type} - {self.track.title}"
    
    def is_positive(self) -> bool:
        return self.feedback_type in ['like', 'save', 'play_full']
    
    def is_negative(self) -> bool:
        return self.feedback_type in ['dislike', 'skip']


class UserExplorationProfile(models.Model):
    """
    User exploration tendency profile
    """
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name='exploration_profile'
    )
    
    preferred_exploration_level = models.FloatField(
        default=0.5,
        help_text="Learned preferred exploration level (0-1)"
    )
    novelty_tolerance = models.FloatField(
        default=0.5,
        help_text="Tolerance for novel/unfamiliar content"
    )
    genre_flexibility = models.FloatField(
        default=0.5,
        help_text="Willingness to explore different genres"
    )
    
    total_feedbacks = models.IntegerField(default=0)
    positive_feedbacks = models.IntegerField(default=0)
    negative_feedbacks = models.IntegerField(default=0)
    deepcut_acceptance_rate = models.FloatField(default=0.5)
    
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'music_user_exploration_profile'
    
    def __str__(self):
        return f"Exploration Profile for {self.user.username}"
    
    def update_from_feedback(self, feedback: RecommendationFeedback):
        """Update profile from feedback"""
        try:
            self.total_feedbacks += 1
            
            if feedback.is_positive():
                self.positive_feedbacks += 1
                if feedback.exploration_level is not None:
                    alpha = 0.1
                    self.preferred_exploration_level = (
                        (1 - alpha) * self.preferred_exploration_level +
                        alpha * feedback.exploration_level
                    )
            elif feedback.is_negative():
                self.negative_feedbacks += 1
                if feedback.exploration_level is not None and feedback.exploration_level > 0.7:
                    alpha = 0.05
                    self.preferred_exploration_level = (
                        (1 - alpha) * self.preferred_exploration_level +
                        alpha * max(0.3, feedback.exploration_level - 0.2)
                    )
            
            if feedback.track.playcount and feedback.track.playcount < 10000:
                if feedback.is_positive():
                    self.deepcut_acceptance_rate = min(1.0,
                        self.deepcut_acceptance_rate * 0.95 + 0.05
                    )
                elif feedback.is_negative():
                    self.deepcut_acceptance_rate = max(0.0,
                        self.deepcut_acceptance_rate * 0.95
                    )
            
            self.save()
        except Exception as e:
            logger.error(f"Error updating exploration profile: {e}")
    
    def get_recommendation_weights(self):
        """Get recommendation weights based on user profile"""
        # Adjust weights based on exploration preferences
        if self.preferred_exploration_level > 0.7:
            # High exploration: prioritize novelty and diversity
            return {
                'similarity': 0.3,
                'novelty': 0.3,
                'popularity': 0.1,
                'diversity': 0.3
            }
        elif self.preferred_exploration_level < 0.3:
            # Low exploration: prioritize similarity and popularity
            return {
                'similarity': 0.6,
                'novelty': 0.05,
                'popularity': 0.25,
                'diversity': 0.1
            }
        else:
            # Balanced weights
            return {
                'similarity': 0.5,
                'novelty': 0.15,
                'popularity': 0.15,
                'diversity': 0.2
            }
