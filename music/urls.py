from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("similar/", views.similar, name="similar"),
    path("artist/<str:name>/", views.artist_detail, name="artist"),
    path("charts/", views.top_tracks, name="charts"),
]
