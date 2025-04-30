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
