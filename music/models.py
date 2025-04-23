from django.db import models


class Artist(models.Model):
    """Basic artist metadata fetched from Last.fm."""

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
    """Track metadata fetched from Last.fm."""

    title = models.CharField(max_length=200)
    artist = models.ForeignKey(Artist, on_delete=models.CASCADE, related_name="tracks")
    mbid = models.CharField(max_length=36, blank=True, null=True)
    url = models.URLField(blank=True)
    playcount = models.PositiveIntegerField(default=0)
    match = models.FloatField(null=True, blank=True)
    fetched_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ("title", "artist")
        ordering = ["-playcount"]

    def __str__(self):
        return f"{self.title} — {self.artist.name}"
