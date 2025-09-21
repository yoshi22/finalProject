from rest_framework import serializers
from music.models import Track, Artist
from music.models_recommendation import SimpleTrackFeatures, UserPreferences, RecommendationLog


class ArtistSerializer(serializers.ModelSerializer):
    class Meta:
        model = Artist
        fields = ['id', 'name', 'popularity', 'genres', 'followers']


class TrackSerializer(serializers.ModelSerializer):
    artist = ArtistSerializer(read_only=True)
    
    class Meta:
        model = Track
        fields = [
            'id', 'name', 'artist', 'album', 'popularity',
            'duration_ms', 'preview_url', 'external_url'
        ]


class SimpleTrackFeaturesSerializer(serializers.ModelSerializer):
    track = TrackSerializer(read_only=True)
    
    class Meta:
        model = SimpleTrackFeatures
        fields = [
            'track', 'energy', 'valence', 'tempo_normalized',
            'danceability', 'acousticness', 'genre_tags',
            'mood_tags', 'popularity_score', 'last_calculated'
        ]


class SimilarTrackSerializer(serializers.Serializer):
    track = TrackSerializer(read_only=True)
    similarity_score = serializers.FloatField()


class RecommendationRequestSerializer(serializers.Serializer):
    seed_track_id = serializers.CharField(required=False)
    limit = serializers.IntegerField(default=20, min_value=1, max_value=100)
    min_similarity = serializers.FloatField(default=0.5, min_value=0.0, max_value=1.0)
    use_diversity = serializers.BooleanField(default=False)
    lambda_param = serializers.FloatField(default=0.7, min_value=0.0, max_value=1.0)
    use_preferences = serializers.BooleanField(default=True)


class UserPreferencesSerializer(serializers.ModelSerializer):
    class Meta:
        model = UserPreferences
        fields = [
            'preferred_energy', 'preferred_valence', 'preferred_tempo',
            'preferred_danceability', 'preferred_acousticness',
            'favorite_genres', 'favorite_moods', 'exploration_level'
        ]


class RecommendationLogSerializer(serializers.ModelSerializer):
    seed_track = TrackSerializer(read_only=True)
    recommended_tracks = TrackSerializer(many=True, read_only=True)
    tracks_played = TrackSerializer(many=True, read_only=True)
    tracks_skipped = TrackSerializer(many=True, read_only=True)
    effectiveness_score = serializers.SerializerMethodField()
    
    class Meta:
        model = RecommendationLog
        fields = [
            'id', 'seed_track', 'recommended_tracks', 'method',
            'similarity_threshold', 'exploration_level',
            'tracks_played', 'tracks_skipped', 'effectiveness_score',
            'created_at'
        ]
    
    def get_effectiveness_score(self, obj):
        score = obj.get_effectiveness_score()
        return round(score, 3) if score is not None else None