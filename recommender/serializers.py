# recommender/serializers.py
from rest_framework import serializers
from .models import Track, Artist

class ArtistSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Artist
        fields = ("spotify_id", "name")

class TrackSerializer(serializers.ModelSerializer):
    artist = ArtistSerializer()
    class Meta:
        model  = Track
        fields = ("spotify_id", "title", "popularity", "artist")
