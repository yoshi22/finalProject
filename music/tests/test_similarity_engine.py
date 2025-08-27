import pytest
from django.test import TestCase
from django.contrib.auth import get_user_model
import numpy as np

from music.models import Track, Artist
from music.models_recommendation import SimpleTrackFeatures, TrackSimilarity
from music.services.similarity_engine import SimilarityEngine, DiversityOptimizer
from music.services.feature_extraction import FeatureExtractor, TagAnalyzer
from music.tests.factories import TrackFactory, ArtistFactory

User = get_user_model()


class TestFeatureExtractor(TestCase):
    """Test feature extraction functionality."""
    
    def setUp(self):
        self.artist = ArtistFactory()
        self.track = TrackFactory(artist=self.artist)
    
    def test_normalize_tempo(self):
        """Test tempo normalization."""
        # Test edge cases
        self.assertEqual(FeatureExtractor.normalize_tempo(0), 0.5)
        self.assertEqual(FeatureExtractor.normalize_tempo(-10), 0.5)
        
        # Test normal range
        self.assertAlmostEqual(FeatureExtractor.normalize_tempo(40), 0.0, places=2)
        self.assertAlmostEqual(FeatureExtractor.normalize_tempo(200), 1.0, places=2)
        self.assertAlmostEqual(FeatureExtractor.normalize_tempo(120), 0.5, places=2)
        
        # Test out of range
        self.assertEqual(FeatureExtractor.normalize_tempo(250), 1.0)
        self.assertEqual(FeatureExtractor.normalize_tempo(30), 0.0)
    
    def test_normalize_popularity(self):
        """Test popularity normalization."""
        self.assertEqual(FeatureExtractor.normalize_popularity(0), 0.0)
        self.assertEqual(FeatureExtractor.normalize_popularity(50), 0.5)
        self.assertEqual(FeatureExtractor.normalize_popularity(100), 1.0)
        self.assertEqual(FeatureExtractor.normalize_popularity(150), 1.0)
    
    def test_extract_track_features(self):
        """Test feature extraction for a track."""
        # Add some attributes to track
        self.track.energy = 0.7
        self.track.valence = 0.6
        self.track.tempo = 120
        self.track.danceability = 0.8
        self.track.acousticness = 0.3
        self.track.popularity = 75
        self.track.save()
        
        # Extract features
        features = FeatureExtractor.extract_track_features(self.track)
        
        self.assertIsNotNone(features)
        self.assertEqual(features.track, self.track)
        self.assertAlmostEqual(features.energy, 0.7, places=2)
        self.assertAlmostEqual(features.valence, 0.6, places=2)
        self.assertAlmostEqual(features.popularity_score, 0.75, places=2)
        
        # Test that features are not duplicated
        features2 = FeatureExtractor.extract_track_features(self.track)
        self.assertEqual(features.id, features2.id)


class TestTagAnalyzer(TestCase):
    """Test tag analysis functionality."""
    
    def test_get_tag_weights(self):
        """Test tag weight calculation."""
        tags = ['rock', 'indie', 'alternative']
        weights = TagAnalyzer.get_tag_weights(tags)
        
        self.assertEqual(weights['rock'], 1.0)
        self.assertAlmostEqual(weights['indie'], 0.5, places=2)
        self.assertAlmostEqual(weights['alternative'], 0.333, places=2)
    
    def test_jaccard_similarity(self):
        """Test Jaccard similarity calculation."""
        tags1 = ['rock', 'indie', 'alternative']
        tags2 = ['rock', 'indie', 'pop']
        tags3 = ['jazz', 'blues']
        tags4 = []
        
        # Some overlap
        similarity = TagAnalyzer.jaccard_similarity(tags1, tags2)
        self.assertAlmostEqual(similarity, 2/4, places=2)  # 2 common, 4 total unique
        
        # No overlap
        similarity = TagAnalyzer.jaccard_similarity(tags1, tags3)
        self.assertEqual(similarity, 0.0)
        
        # Empty tags
        similarity = TagAnalyzer.jaccard_similarity(tags1, tags4)
        self.assertEqual(similarity, 0.0)
        
        # Identical tags
        similarity = TagAnalyzer.jaccard_similarity(tags1, tags1)
        self.assertEqual(similarity, 1.0)
    
    def test_weighted_tag_similarity(self):
        """Test weighted tag similarity."""
        tags1 = ['rock', 'indie', 'alternative']
        tags2 = ['rock', 'alternative', 'indie']  # Different order
        
        similarity = TagAnalyzer.weighted_tag_similarity(tags1, tags2)
        self.assertGreater(similarity, 0.0)
        self.assertLessEqual(similarity, 1.0)


class TestSimilarityEngine(TestCase):
    """Test similarity calculation engine."""
    
    def setUp(self):
        # Create test tracks with features
        self.artist = ArtistFactory()
        self.track1 = TrackFactory(artist=self.artist)
        self.track2 = TrackFactory(artist=self.artist)
        self.track3 = TrackFactory(artist=self.artist)
        
        # Create features for tracks
        self.features1 = SimpleTrackFeatures.objects.create(
            track=self.track1,
            energy=0.8,
            valence=0.7,
            tempo_normalized=0.6,
            danceability=0.8,
            acousticness=0.2,
            popularity_score=0.9,
            genre_tags=['rock', 'indie'],
            mood_tags=['energetic', 'upbeat']
        )
        
        self.features2 = SimpleTrackFeatures.objects.create(
            track=self.track2,
            energy=0.7,
            valence=0.8,
            tempo_normalized=0.65,
            danceability=0.75,
            acousticness=0.3,
            popularity_score=0.85,
            genre_tags=['rock', 'alternative'],
            mood_tags=['energetic', 'driving']
        )
        
        self.features3 = SimpleTrackFeatures.objects.create(
            track=self.track3,
            energy=0.2,
            valence=0.3,
            tempo_normalized=0.3,
            danceability=0.2,
            acousticness=0.9,
            popularity_score=0.4,
            genre_tags=['jazz', 'blues'],
            mood_tags=['mellow', 'relaxing']
        )
    
    def test_calculate_audio_similarity(self):
        """Test audio feature similarity calculation."""
        similarity = SimilarityEngine._calculate_audio_similarity(
            self.features1, self.features2
        )
        
        # Should be high similarity (similar features)
        self.assertGreater(similarity, 0.8)
        self.assertLessEqual(similarity, 1.0)
        
        # Test dissimilar tracks
        similarity = SimilarityEngine._calculate_audio_similarity(
            self.features1, self.features3
        )
        
        # Should be low similarity
        self.assertLess(similarity, 0.5)
    
    def test_calculate_tag_similarity(self):
        """Test tag similarity calculation."""
        similarity = SimilarityEngine._calculate_tag_similarity(
            self.features1, self.features2
        )
        
        # Should have some similarity (shared tags)
        self.assertGreater(similarity, 0.0)
        
        # Test no overlap
        similarity = SimilarityEngine._calculate_tag_similarity(
            self.features1, self.features3
        )
        
        # Should have no similarity
        self.assertEqual(similarity, 0.0)
    
    def test_calculate_track_similarity(self):
        """Test overall track similarity calculation."""
        similarity = SimilarityEngine.calculate_track_similarity(
            self.track1, self.track2
        )
        
        self.assertIsNotNone(similarity)
        self.assertGreater(similarity, 0.5)  # Should be similar
        self.assertLessEqual(similarity, 1.0)
        
        # Test dissimilar tracks
        similarity = SimilarityEngine.calculate_track_similarity(
            self.track1, self.track3
        )
        
        self.assertIsNotNone(similarity)
        self.assertLess(similarity, 0.5)  # Should be dissimilar
    
    def test_find_similar_tracks(self):
        """Test finding similar tracks."""
        # Create more tracks for testing
        for i in range(5):
            track = TrackFactory(artist=self.artist)
            SimpleTrackFeatures.objects.create(
                track=track,
                energy=0.7 + np.random.random() * 0.2,
                valence=0.6 + np.random.random() * 0.2,
                tempo_normalized=0.5 + np.random.random() * 0.2,
                danceability=0.7 + np.random.random() * 0.2,
                acousticness=0.2 + np.random.random() * 0.2,
                popularity_score=0.8,
                genre_tags=['rock'],
                mood_tags=['energetic']
            )
        
        # Find similar tracks
        similar_tracks = SimilarityEngine.find_similar_tracks(
            self.track1, limit=5, min_similarity=0.3
        )
        
        self.assertIsNotNone(similar_tracks)
        self.assertGreater(len(similar_tracks), 0)
        self.assertLessEqual(len(similar_tracks), 5)
        
        # Check ordering (should be sorted by similarity)
        if len(similar_tracks) > 1:
            for i in range(len(similar_tracks) - 1):
                self.assertGreaterEqual(
                    similar_tracks[i][1],
                    similar_tracks[i + 1][1]
                )


class TestDiversityOptimizer(TestCase):
    """Test recommendation diversity optimization."""
    
    def setUp(self):
        # Create test tracks
        self.artist = ArtistFactory()
        self.tracks = []
        
        for i in range(10):
            track = TrackFactory(artist=self.artist)
            features = SimpleTrackFeatures.objects.create(
                track=track,
                energy=0.5 + (i * 0.05),
                valence=0.5,
                tempo_normalized=0.5,
                danceability=0.5,
                acousticness=0.5,
                popularity_score=0.9 - (i * 0.05),
                genre_tags=['rock'] if i < 5 else ['pop'],
                mood_tags=['upbeat']
            )
            self.tracks.append((track, 0.9 - i * 0.05))  # Decreasing similarity
    
    def test_apply_mmr(self):
        """Test Maximal Marginal Relevance application."""
        # Test with high lambda (focus on relevance)
        results = DiversityOptimizer.apply_mmr(
            self.tracks, lambda_param=0.9, num_results=5
        )
        
        self.assertEqual(len(results), 5)
        # First track should be the most relevant
        self.assertEqual(results[0][0], self.tracks[0][0])
        
        # Test with low lambda (focus on diversity)
        results = DiversityOptimizer.apply_mmr(
            self.tracks, lambda_param=0.1, num_results=5
        )
        
        self.assertEqual(len(results), 5)
        # Results should be more diverse
        
    def test_apply_mmr_empty_list(self):
        """Test MMR with empty input."""
        results = DiversityOptimizer.apply_mmr([], lambda_param=0.5, num_results=5)
        self.assertEqual(results, [])
    
    def test_apply_mmr_single_track(self):
        """Test MMR with single track."""
        results = DiversityOptimizer.apply_mmr(
            [self.tracks[0]], lambda_param=0.5, num_results=5
        )
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], self.tracks[0])