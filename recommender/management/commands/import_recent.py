# recommender/management/commands/import_recent.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from recommender.spotify import get_user_client_cli
from recommender.models import Track, Listen
from django.utils import timezone

class Command(BaseCommand):
    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, username, *args, **opts):
        user = User.objects.get(username=username)
        sp   = get_user_client_cli()         # 個人トークン前提
        items = sp.current_user_recently_played(limit=50)["items"]
        for it in items:
            tid = it["track"]["id"]
            track = Track.objects.filter(spotify_id=tid).first()
            if not track:
                continue
            Listen.objects.get_or_create(
                user=user, track=track,
                played_at=timezone.datetime.fromtimestamp(
                    it["played_at_ts"], tz=timezone.utc)
            )
        self.stdout.write(self.style.SUCCESS("imported recent plays"))
