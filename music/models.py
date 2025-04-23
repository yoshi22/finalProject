from django.db import models

# Create your models here.
from django.db import models

class Artist(models.Model):
    name       = models.CharField(max_length=200, unique=True)
    mbid       = models.CharField(max_length=36, blank=True, null=True)  # MusicBrainz ID
    url        = models.URLField(blank=True)
    listeners  = models.PositiveIntegerField(default=0)
    playcount  = models.PositiveIntegerField(default=0)
    summary    = models.TextField(blank=True)            # wiki サマリ
    fetched_at = models.DateTimeField(auto_now=True)     # 取得日時

    def __str__(self):
        return self.name

class Track(models.Model):
    title      = models.CharField(max_length=200)
    artist     = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="tracks")
    mbid       = models.CharField(max_length=36, blank=True, null=True)
    url        = models.URLField(blank=True)
    playcount  = models.PositiveIntegerField(default=0)  # chart 情報用
    match      = models.FloatField(null=True, blank=True)  # 類似度 track.getSimilar 用
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("title", "artist")            # 同一曲の重複防止
        ordering = ["-playcount"]

    def __str__(self):
        return f"{self.title} — {self.artist.name}"
