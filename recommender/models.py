from django.db import models
from django.contrib.auth.models import User
from json import loads, dumps

class Artist(models.Model):
    spotify_id  = models.CharField(max_length=32, unique=True)
    name        = models.CharField(max_length=200)
    genres_json = models.TextField(default="[]")     # JSON 配列

    @property
    def genres(self):        # python からは list として使える
        return loads(self.genres_json)

class Track(models.Model):
    spotify_id = models.CharField(max_length=32, unique=True)
    title      = models.CharField(max_length=255)
    artist     = models.ForeignKey(Artist, on_delete=models.CASCADE)
    popularity = models.PositiveSmallIntegerField(default=0)
    features   = models.TextField()                  # JSON list [danceability, energy, ...]
    # インデックス
    class Meta:
        indexes = [models.Index(fields=["artist"]),]

class UserProfile(models.Model):
    """OAuth トークン & 好み情報"""
    user             = models.OneToOneField(User, on_delete=models.CASCADE)
    sp_access_token  = models.CharField(max_length=255)
    sp_refresh_token = models.CharField(max_length=255)
    token_expires    = models.DateTimeField()

class Listen(models.Model):
    user       = models.ForeignKey(User, on_delete=models.CASCADE)
    track      = models.ForeignKey(Track, on_delete=models.CASCADE)
    played_at  = models.DateTimeField()
    rating     = models.PositiveSmallIntegerField(null=True, blank=True)  # ★任意
    class Meta:
        unique_together = ("user", "track", "played_at")