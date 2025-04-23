from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),
    path("search/", views.track_search, name="search"),
    path("similar/", views.similar, name="similar"),
    path("recommend/", views.recommend, name="recommend"),  # ★追加
    path("artist/<str:name>/", views.artist_detail, name="artist"),
    path("charts/", views.live_chart, name="charts"),
]
