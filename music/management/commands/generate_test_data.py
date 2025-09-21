from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from music.tests.factories import (
    UserFactory,
    ArtistFactory,
    TrackFactory,
    PlaylistFactory,
    PlaylistTrackFactory,
    VocalProfileFactory,
)
import random
from datetime import datetime, timedelta

User = get_user_model()


class Command(BaseCommand):
    help = "Generate test data for development and testing"

    def add_arguments(self, parser):
        parser.add_argument(
            "--users",
            type=int,
            default=10,
            help="Number of users to create",
        )
        parser.add_argument(
            "--artists",
            type=int,
            default=50,
            help="Number of artists to create",
        )
        parser.add_argument(
            "--tracks",
            type=int,
            default=500,
            help="Number of tracks to create",
        )
        parser.add_argument(
            "--playlists",
            type=int,
            default=20,
            help="Number of playlists to create",
        )
        parser.add_argument(
            "--vocal-profiles",
            type=int,
            default=30,
            help="Number of vocal profiles to create",
        )
        parser.add_argument(
            "--clear",
            action="store_true",
            help="Clear existing data before generating new data",
        )

    def handle(self, *args, **options):
        if options["clear"]:
            self.stdout.write("Clearing existing data...")
            from music.models import PlaylistTrack, Playlist, Track, Artist, VocalProfile
            
            PlaylistTrack.objects.all().delete()
            Playlist.objects.all().delete()
            VocalProfile.objects.all().delete()
            Track.objects.all().delete()
            Artist.objects.all().delete()
            User.objects.filter(is_superuser=False).delete()
            self.stdout.write(self.style.SUCCESS("Existing data cleared"))

        # Generate users
        self.stdout.write(f"Creating {options['users']} users...")
        users = []
        for _ in range(options["users"]):
            users.append(UserFactory())
        self.stdout.write(self.style.SUCCESS(f"Created {len(users)} users"))

        # Generate artists
        self.stdout.write(f"Creating {options['artists']} artists...")
        artists = []
        for _ in range(options["artists"]):
            artists.append(ArtistFactory())
        self.stdout.write(self.style.SUCCESS(f"Created {len(artists)} artists"))

        # Generate tracks
        self.stdout.write(f"Creating {options['tracks']} tracks...")
        tracks = []
        for _ in range(options["tracks"]):
            artist = random.choice(artists)
            tracks.append(TrackFactory(artist=artist))
        self.stdout.write(self.style.SUCCESS(f"Created {len(tracks)} tracks"))

        # Generate playlists
        self.stdout.write(f"Creating {options['playlists']} playlists...")
        playlists = []
        for _ in range(options["playlists"]):
            user = random.choice(users)
            playlist = PlaylistFactory(owner=user)
            playlists.append(playlist)
            
            # Add random tracks to playlist
            num_tracks = random.randint(5, 50)
            playlist_tracks = random.sample(tracks, min(num_tracks, len(tracks)))
            for i, track in enumerate(playlist_tracks):
                PlaylistTrackFactory(
                    playlist=playlist,
                    track=track,
                    position=i
                )
        self.stdout.write(self.style.SUCCESS(f"Created {len(playlists)} playlists"))

        # Generate vocal profiles
        self.stdout.write(f"Creating {options['vocal_profiles']} vocal profiles...")
        vocal_profiles = []
        users_sample = random.sample(users, min(options["vocal_profiles"], len(users)))
        for user in users_sample:
            vocal_profiles.append(VocalProfileFactory(user=user))
        self.stdout.write(self.style.SUCCESS(f"Created {len(vocal_profiles)} vocal profiles"))

        # Summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("Test data generation complete!"))
        self.stdout.write(f"Users: {len(users)}")
        self.stdout.write(f"Artists: {len(artists)}")
        self.stdout.write(f"Tracks: {len(tracks)}")
        self.stdout.write(f"Playlists: {len(playlists)}")
        self.stdout.write(f"Vocal Profiles: {len(vocal_profiles)}")
        self.stdout.write("=" * 50)