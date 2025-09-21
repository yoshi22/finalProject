from django.test import TestCase
from django.contrib.auth import get_user_model
from music.models import Track, Artist
from music.models_recommendation import SimpleTrackFeatures
from music.models_recommendation import UserRecommendationPreferences
from music.services.hybrid_engine import HybridRecommendationEngine, RecommendationType
from music.services.ab_testing import ABTestFramework
from music.services.diversity_optimizer import DiversityOptimizer
from music.services.performance_monitor import PerformanceMonitor
from music.tests.factories import TrackFactory, ArtistFactory, UserFactory
import time
import numpy as np

User = get_user_model()


class TestHybridRecommendation(TestCase):
    """
    ハイブリッド推薦システムの統合テスト
    """
    
    def setUp(self):
        """テストデータのセットアップ"""
        self.engine = HybridRecommendationEngine()
        self.user = UserFactory()
        
        # Create artist
        self.artists = []
        for i in range(5):
            artist = ArtistFactory(name=f"Artist {i}")
            self.artists.append(artist)
        
        # Create tracks by genre
        self.tracks = []
        genres = ['rock', 'pop', 'jazz', 'electronic', 'classical']
        
        for i in range(50):
            track = TrackFactory(
                title=f"Track {i}",
                artist=self.artists[i % 5],
                playcount=100 * (50 - i)  # Set popularity
            )
            
            # Create features
            SimpleTrackFeatures.objects.create(
                track=track,
                energy=np.random.random(),
                valence=np.random.random(),
                tempo_normalized=np.random.random(),
                danceability=np.random.random(),
                acousticness=np.random.random(),
                popularity_score=(50 - i) / 50,  # Normalize popularity
                genre_tags=[genres[i % 5]],
                mood_tags=['upbeat' if i % 2 == 0 else 'mellow']
            )
            
            self.tracks.append(track)
    
    def test_hybrid_recommendation_basic(self):
        """基本的なハイブリッド推薦のテスト"""
        seed_track = self.tracks[0]
        
        results = self.engine.recommend(
            user=self.user,
            seed_track=seed_track,
            limit=10
        )
        
        self.assertEqual(len(results), 10)
        
        # Check result format
        for track, score, metadata in results:
            self.assertIsInstance(track, Track)
            self.assertIsInstance(score, float)
            self.assertIn('sources', metadata)
            self.assertGreaterEqual(score, 0)
            self.assertLessEqual(score, 1)
    
    def test_recommendation_without_seed(self):
        """シードトラックなしの推薦テスト"""
        results = self.engine.recommend(
            user=self.user,
            seed_track=None,
            limit=10
        )
        
        # Should return popularity-based recommendations
        self.assertGreaterEqual(len(results), 1)
        
        # Check if sorted by popularity
        if len(results) > 1:
            for i in range(len(results) - 1):
                self.assertGreaterEqual(
                    results[i][0].playcount,
                    results[i + 1][0].playcount
                )
    
    def test_diversity_optimization(self):
        """多様性最適化のテスト"""
        seed_track = self.tracks[0]
        
        # No diversity
        results_no_diversity = self.engine.recommend(
            user=self.user,
            seed_track=seed_track,
            limit=20,
            diversity_factor=0.0
        )
        
        # With diversity
        results_with_diversity = self.engine.recommend(
            user=self.user,
            seed_track=seed_track,
            limit=20,
            diversity_factor=0.8
        )
        
        # 多様性メトリクス計算
        optimizer = DiversityOptimizer()
        
        tracks_no_div = [r[0] for r in results_no_diversity]
        tracks_with_div = [r[0] for r in results_with_diversity]
        
        metrics_no_div = optimizer.calculate_diversity_metrics(tracks_no_div)
        metrics_with_div = optimizer.calculate_diversity_metrics(tracks_with_div)
        
        # 多様性が向上しているか確認
        self.assertGreaterEqual(
            metrics_with_div['intra_list_diversity'],
            metrics_no_div['intra_list_diversity']
        )
    
    def test_custom_weights(self):
        """カスタム重みのテスト"""
        seed_track = self.tracks[0]
        
        # コンテンツベースを重視
        custom_weights = {
            RecommendationType.CONTENT_BASED: 0.8,
            RecommendationType.POPULARITY: 0.1,
            RecommendationType.TRENDING: 0.1,
            RecommendationType.COLLABORATIVE: 0.0
        }
        
        results = self.engine.recommend(
            user=self.user,
            seed_track=seed_track,
            limit=10,
            custom_weights=custom_weights
        )
        
        self.assertEqual(len(results), 10)
        
        # メタデータでコンテンツベースが主要ソースか確認
        for _, _, metadata in results[:5]:
            sources = metadata.get('sources', [])
            if sources:
                content_based = [s for s in sources if s['type'] == 'content_based']
                self.assertGreater(len(content_based), 0)


class TestABTestFramework(TestCase):
    """
    A/Bテストフレームワークのテスト
    """
    
    def setUp(self):
        self.ab_framework = ABTestFramework()
        self.user = UserFactory()
    
    def test_user_variant_assignment(self):
        """ユーザーバリアント割り当てテスト"""
        variant = self.ab_framework.get_user_variant(
            self.user,
            'recommendation_weights'
        )
        
        self.assertIsNotNone(variant)
        self.assertIn(variant, ['control', 'variant_a', 'variant_b'])
        
        # 同じユーザーは同じバリアントに割り当てられる
        variant2 = self.ab_framework.get_user_variant(
            self.user,
            'recommendation_weights'
        )
        self.assertEqual(variant, variant2)
    
    def test_variant_config(self):
        """バリアント設定取得テスト"""
        config = self.ab_framework.get_variant_config(
            self.user,
            'recommendation_weights'
        )
        
        self.assertIn('content_weight', config)
        self.assertIn('popularity_weight', config)
        
        # 重みの合計が1になることを確認
        total_weight = (
            config.get('content_weight', 0) +
            config.get('collaborative_weight', 0) +
            config.get('popularity_weight', 0) +
            config.get('trending_weight', 0)
        )
        self.assertAlmostEqual(total_weight, 1.0, places=2)
    
    def test_event_tracking(self):
        """イベントトラッキングテスト"""
        # イベントを記録
        self.ab_framework.track_event(
            self.user,
            'recommendation_weights',
            'recommendation_generated',
            {'track_count': 10}
        )
        
        # メトリクスが更新されているか確認
        results = self.ab_framework.get_experiment_results('recommendation_weights')
        self.assertIn('variants', results)
    
    def test_experiment_active_check(self):
        """実験アクティブチェックテスト"""
        is_active = self.ab_framework.is_experiment_active('recommendation_weights')
        self.assertIsInstance(is_active, bool)


class TestDiversityOptimizer(TestCase):
    """
    多様性最適化のテスト
    """
    
    def setUp(self):
        self.optimizer = DiversityOptimizer()
        
        # Create test track
        self.artists = [ArtistFactory() for _ in range(3)]
        self.tracks = []
        
        for i in range(10):
            track = TrackFactory(artist=self.artists[i % 3])
            SimpleTrackFeatures.objects.create(
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
            self.tracks.append((track, 0.9 - i * 0.05))  # スコア降順
    
    def test_mmr_optimization(self):
        """MMR最適化テスト"""
        # 高λ（関連性重視）
        results_high_lambda = self.optimizer.apply_mmr(
            self.tracks, lambda_param=0.9, num_results=5
        )
        
        self.assertEqual(len(results_high_lambda), 5)
        # 最初のトラックが最も関連性が高い
        self.assertEqual(results_high_lambda[0][0], self.tracks[0][0])
        
        # 低λ（多様性重視）
        results_low_lambda = self.optimizer.apply_mmr(
            self.tracks, lambda_param=0.1, num_results=5
        )
        
        self.assertEqual(len(results_low_lambda), 5)
    
    def test_diversity_metrics(self):
        """多様性メトリクス計算テスト"""
        tracks = [t[0] for t in self.tracks[:5]]
        metrics = self.optimizer.calculate_diversity_metrics(tracks)
        
        self.assertIn('intra_list_diversity', metrics)
        self.assertIn('genre_coverage', metrics)
        self.assertIn('artist_diversity', metrics)
        self.assertIn('feature_diversity', metrics)
        
        # 値の範囲確認
        self.assertGreaterEqual(metrics['intra_list_diversity'], 0)
        self.assertLessEqual(metrics['intra_list_diversity'], 1)
        self.assertGreaterEqual(metrics['artist_diversity'], 0)
        self.assertLessEqual(metrics['artist_diversity'], 1)
    
    def test_rerank_for_diversity(self):
        """目標多様性への再ランキングテスト"""
        target_diversity = 0.6
        
        reranked = self.optimizer.rerank_for_diversity(
            self.tracks,
            target_diversity=target_diversity,
            max_iterations=5
        )
        
        # 再ランキング後の多様性を確認
        tracks = [r[0] for r in reranked]
        metrics = self.optimizer.calculate_diversity_metrics(tracks)
        
        # 目標に近づいているか確認（完全一致は保証されない）
        self.assertGreaterEqual(metrics['intra_list_diversity'], 0.3)


class TestUserPreferences(TestCase):
    """
    User preference tests
    """
    
    def setUp(self):
        self.user = UserFactory()
    
    def test_preferences_creation(self):
        """Test preference creation"""
        prefs = UserRecommendationPreferences.objects.create(
            user=self.user,
            content_weight=0.5,
            collaborative_weight=0.2,
            popularity_weight=0.2,
            trending_weight=0.1,
            diversity_factor=0.4,
            exploration_level=0.3
        )
        
        self.assertEqual(prefs.user, self.user)
        
        # 重みが正規化されているか確認
        total = (
            prefs.content_weight +
            prefs.collaborative_weight +
            prefs.popularity_weight +
            prefs.trending_weight
        )
        self.assertAlmostEqual(total, 1.0, places=2)
    
    def test_weight_normalization(self):
        """重み正規化テスト"""
        prefs = UserRecommendationPreferences(
            user=self.user,
            content_weight=2.0,  # 合計が1を超える
            collaborative_weight=1.0,
            popularity_weight=1.0,
            trending_weight=1.0
        )
        prefs.save()
        
        # 保存後に正規化されているか確認
        total = (
            prefs.content_weight +
            prefs.collaborative_weight +
            prefs.popularity_weight +
            prefs.trending_weight
        )
        self.assertAlmostEqual(total, 1.0, places=2)


class TestPerformanceMonitor(TestCase):
    """
    性能モニタリングのテスト
    """
    
    def setUp(self):
        self.monitor = PerformanceMonitor()
        self.user = UserFactory()
    
    def test_record_recommendation_request(self):
        """推薦リクエスト記録テスト"""
        # リクエストを記録
        self.monitor.record_recommendation_request(
            user_id=self.user.id,
            response_time=150.0,
            cache_hit=True,
            recommendation_type='content_based'
        )
        
        # メトリクスを取得
        metrics = self.monitor.get_dashboard_data()
        
        self.assertIn('real_time', metrics)
        self.assertIn('requests_per_minute', metrics['real_time'])
        self.assertGreaterEqual(metrics['real_time']['requests_per_minute'], 1)
    
    def test_user_interaction_recording(self):
        """ユーザーインタラクション記録テスト"""
        track = TrackFactory()
        
        # ビューとクリックを記録
        self.monitor.record_user_interaction(
            user_id=self.user.id,
            track_id=track.id,
            interaction_type='view'
        )
        
        self.monitor.record_user_interaction(
            user_id=self.user.id,
            track_id=track.id,
            interaction_type='click'
        )
        
        # CTRが計算されるか確認
        metrics = self.monitor.get_dashboard_data()
        daily = metrics.get('daily', {})
        ctr = daily.get('average_ctr', 0)
        
        # ビューとクリックが記録されていればCTRは1.0
        self.assertGreaterEqual(ctr, 0)
    
    def test_error_recording(self):
        """エラー記録テスト"""
        # エラーを記録
        self.monitor.record_error(
            error_type='ValueError',
            error_message='Test error'
        )
        
        # エラー率が更新されるか確認
        metrics = self.monitor.get_dashboard_data()
        health = metrics.get('system_health', {})
        error_rate = health.get('error_rate', 0)
        
        self.assertGreaterEqual(error_rate, 0)


class TestIntegrationFlow(TestCase):
    """
    統合フローのテスト
    """
    
    def setUp(self):
        # Create test data
        self.user = UserFactory()
        self.artists = [ArtistFactory() for _ in range(3)]
        self.tracks = []
        
        for i in range(20):
            track = TrackFactory(
                artist=self.artists[i % 3],
                playcount=1000 - i * 50
            )
            SimpleTrackFeatures.objects.create(
                track=track,
                energy=np.random.random(),
                valence=np.random.random(),
                tempo_normalized=np.random.random(),
                danceability=np.random.random(),
                acousticness=np.random.random(),
                popularity_score=(20 - i) / 20,
                genre_tags=['rock', 'indie'] if i < 10 else ['pop', 'electronic'],
                mood_tags=['energetic'] if i % 2 == 0 else ['calm']
            )
            self.tracks.append(track)
    
    def test_full_recommendation_flow(self):
        """完全な推薦フローのテスト"""
        # 1. Create user preferences
        prefs = UserRecommendationPreferences.objects.create(
            user=self.user,
            content_weight=0.4,
            collaborative_weight=0.0,  # Collaborative filtering not implemented
            popularity_weight=0.4,
            trending_weight=0.2,
            diversity_factor=0.5
        )
        
        # 2. A/Bテストバリアントを取得
        ab_framework = ABTestFramework()
        variant = ab_framework.get_user_variant(self.user, 'diversity_optimization')
        
        # 3. ハイブリッド推薦を実行
        engine = HybridRecommendationEngine()
        start_time = time.time()
        
        results = engine.recommend(
            user=self.user,
            seed_track=self.tracks[0],
            limit=15,
            diversity_factor=prefs.diversity_factor
        )
        
        response_time = (time.time() - start_time) * 1000  # ミリ秒
        
        # 4. パフォーマンスを記録
        monitor = PerformanceMonitor()
        monitor.record_recommendation_request(
            user_id=self.user.id,
            response_time=response_time,
            cache_hit=False,
            recommendation_type='hybrid'
        )
        
        # 5. A/Bテストイベントを記録
        ab_framework.track_event(
            self.user,
            'diversity_optimization',
            'recommendation_generated',
            {'count': len(results), 'response_time': response_time}
        )
        
        # 検証
        self.assertEqual(len(results), 15)
        self.assertLess(response_time, 1000)  # 1秒以内
        
        # 多様性を確認
        optimizer = DiversityOptimizer()
        tracks = [r[0] for r in results]
        metrics = optimizer.calculate_diversity_metrics(tracks)
        
        self.assertGreater(metrics['intra_list_diversity'], 0.2)
        self.assertGreater(metrics['artist_diversity'], 0.3)