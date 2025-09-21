import factory
from factory.django import DjangoModelFactory
from faker import Faker
from music.models import Track, Artist, Playlist, PlaylistTrack, VocalProfile
from django.contrib.auth import get_user_model

fake = Faker()
User = get_user_model()


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"user_{n}")
    email = factory.LazyAttribute(lambda obj: f"{obj.username}@example.com")
    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")


class ArtistFactory(DjangoModelFactory):
    class Meta:
        model = Artist

    name = factory.Faker("name")
    mbid = factory.Faker("uuid4")
    url = factory.Faker("url")
    listeners = factory.Faker("random_int", min=100, max=1000000)
    playcount = factory.Faker("random_int", min=1000, max=10000000)
    summary = factory.Faker("text", max_nb_chars=200)


class TrackFactory(DjangoModelFactory):
    class Meta:
        model = Track

    title = factory.Faker("sentence", nb_words=4)
    artist = factory.SubFactory(ArtistFactory)
    mbid = factory.Faker("uuid4")
    url = factory.Faker("url")
    playcount = factory.Faker("random_int", min=0, max=100000)
    match = factory.Faker("pyfloat", min_value=0.0, max_value=1.0)
    preview_url = factory.Faker("url")
    
    # Note: Audio features should be stored in SimpleTrackFeatures, not in Track model
    # These will be created separately


class PlaylistFactory(DjangoModelFactory):
    class Meta:
        model = Playlist

    owner = factory.SubFactory(UserFactory)
    name = factory.Faker("sentence", nb_words=3)


class PlaylistTrackFactory(DjangoModelFactory):
    class Meta:
        model = PlaylistTrack

    playlist = factory.SubFactory(PlaylistFactory)
    track = factory.SubFactory(TrackFactory)
    position = factory.Sequence(lambda n: n)


class VocalProfileFactory(DjangoModelFactory):
    class Meta:
        model = VocalProfile

    user = factory.SubFactory(UserFactory)
    note_min = factory.Faker("random_int", min=48, max=60)  # C3 to C4
    note_max = factory.Faker("random_int", min=72, max=96)  # C5 to C7