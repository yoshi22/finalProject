from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("search/", views.track_search, name="search"),
    path("similar/", views.similar, name="similar"),
    path("deepcut/", views.deepcut, name="deepcut"),          # ★追加
    path("track/<str:artist>/<str:title>/", views.track_detail, name="track_detail"),
    path("artist/<str:name>/", views.artist_detail, name="artist"),
    path("charts/", views.live_chart, name="charts"),

    path("signup/", views.signup, name="signup"),

    # playlist
    path("playlists/", views.playlist_list, name="playlist_list"),
    path("playlists/create/", views.playlist_create, name="playlist_create"),
    path("playlists/<int:pk>/", views.playlist_detail, name="playlist_detail"),
    path("playlist/add/", views.add_to_playlist, name="playlist_add"),
]
