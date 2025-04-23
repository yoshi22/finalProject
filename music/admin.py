from django.contrib import admin
from .models import Artist, Track, Playlist, PlaylistTrack

admin.site.register(Artist)
admin.site.register(Track)
admin.site.register(Playlist)
admin.site.register(PlaylistTrack)
