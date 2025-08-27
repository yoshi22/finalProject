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

    id = factory.Sequence(lambda n: f"artist_{n}")
    name = factory.Faker("name")
    popularity = factory.Faker("random_int", min=0, max=100)
    followers = factory.Faker("random_int", min=0, max=1000000)
    genres = factory.LazyFunction(
        lambda: ",".join(fake.random_choices(
            elements=("rock", "pop", "jazz", "electronic", "hip-hop", "classical"),
            length=fake.random_int(1, 3),
        ))
    )


class TrackFactory(DjangoModelFactory):
    class Meta:
        model = Track

    id = factory.Sequence(lambda n: f"track_{n}")
    name = factory.Faker("sentence", nb_words=4)
    artist = factory.SubFactory(ArtistFactory)
    album = factory.Faker("sentence", nb_words=3)
    popularity = factory.Faker("random_int", min=0, max=100)
    duration_ms = factory.Faker("random_int", min=30000, max=600000)
    
    # Audio features
    acousticness = factory.Faker("pyfloat", min_value=0.0, max_value=1.0)
    danceability = factory.Faker("pyfloat", min_value=0.0, max_value=1.0)
    energy = factory.Faker("pyfloat", min_value=0.0, max_value=1.0)
    instrumentalness = factory.Faker("pyfloat", min_value=0.0, max_value=1.0)
    key = factory.Faker("random_int", min=0, max=11)
    liveness = factory.Faker("pyfloat", min_value=0.0, max_value=1.0)
    loudness = factory.Faker("pyfloat", min_value=-60.0, max_value=0.0)
    mode = factory.Faker("random_int", min=0, max=1)
    speechiness = factory.Faker("pyfloat", min_value=0.0, max_value=1.0)
    tempo = factory.Faker("pyfloat", min_value=50.0, max_value=200.0)
    time_signature = factory.Faker("random_element", elements=[3, 4, 5, 7])
    valence = factory.Faker("pyfloat", min_value=0.0, max_value=1.0)
    
    preview_url = factory.Faker("url")
    external_url = factory.Faker("url")


class PlaylistFactory(DjangoModelFactory):
    class Meta:
        model = Playlist

    user = factory.SubFactory(UserFactory)
    name = factory.Faker("sentence", nb_words=3)
    description = factory.Faker("text", max_nb_chars=200)
    is_public = factory.Faker("boolean")


class PlaylistTrackFactory(DjangoModelFactory):
    class Meta:
        model = PlaylistTrack

    playlist = factory.SubFactory(PlaylistFactory)
    track = factory.SubFactory(TrackFactory)
    added_at = factory.Faker("date_time_this_year")
    order = factory.Sequence(lambda n: n)


class VocalProfileFactory(DjangoModelFactory):
    class Meta:
        model = VocalProfile

    artist = factory.SubFactory(ArtistFactory)
    highest_note = factory.Faker("random_element", elements=["C5", "D5", "E5", "F5", "G5", "A5", "B5"])
    lowest_note = factory.Faker("random_element", elements=["E2", "F2", "G2", "A2", "B2", "C3", "D3"])
    vocal_range_octaves = factory.Faker("pyfloat", min_value=1.5, max_value=5.0)
    voice_type = factory.Faker("random_element", elements=["Soprano", "Mezzo-Soprano", "Alto", "Tenor", "Baritone", "Bass"])
    technique_level = factory.Faker("random_element", elements=["Beginner", "Intermediate", "Advanced", "Professional", "Master"])
    genres = factory.LazyFunction(
        lambda: ",".join(fake.random_choices(
            elements=("rock", "pop", "jazz", "classical", "r&b", "opera"),
            length=fake.random_int(1, 3),
        ))
    )