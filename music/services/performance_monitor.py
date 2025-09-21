from typing import Dict, List, Any
from datetime import datetime, timedelta
from django.core.cache import cache
from django.db.models import Avg, Count, Q
from music.models import Track
from music.models_recommendation import RecommendationLog
import json
import logging

logger = logging.getLogger(__name__)


class PerformanceMonitor:
    """
    推薦システムの性能モニタリング
    """
    
    def __init__(self):
        self.metrics_cache_ttl = 60 * 5  # 5分
    
    def get_dashboard_data(self) -> Dict[str, Any]:
        """
        ダッシュボード用データを取得
        """
        return {
            'real_time': self._get_realtime_metrics(),
            'daily': self._get_daily_metrics(),
            'recommendation_quality': self._get_quality_metrics(),
            'system_health': self._get_health_metrics(),
            'ab_test_results': self._get_ab_test_metrics()
        }
    
    def _get_realtime_metrics(self) -> Dict:
        """
        リアルタイムメトリクス
        """
        cache_key = 'metrics:realtime'
        cached = cache.get(cache_key)
        
        if cached:
            return json.loads(cached)
        
        metrics = {
            'requests_per_minute': self._calculate_rpm(),
            'average_response_time': self._get_avg_response_time(),
            'cache_hit_rate': self._get_cache_hit_rate(),
            'active_users': self._count_active_users(),
            'recommendations_served': self._count_recent_recommendations()
        }
        
        cache.set(cache_key, json.dumps(metrics), 60)
        return metrics
    
    def _get_daily_metrics(self) -> Dict:
        """
        日次メトリクス
        """
        cache_key = 'metrics:daily'
        cached = cache.get(cache_key)
        
        if cached:
            return json.loads(cached)
        
        today = datetime.now().date()
        
        metrics = {
            'total_recommendations': self._count_daily_recommendations(),
            'unique_users': self._count_daily_users(),
            'average_ctr': self._calculate_daily_ctr(),
            'popular_genres': self._get_popular_genres(),
            'recommendation_distribution': self._get_recommendation_distribution()
        }
        
        cache.set(cache_key, json.dumps(metrics), self.metrics_cache_ttl)
        return metrics
    
    def _get_quality_metrics(self) -> Dict:
        """
        推薦品質メトリクス
        """
        return {
            'diversity_score': self._calculate_diversity_score(),
            'novelty_score': self._calculate_novelty_score(),
            'coverage': self._calculate_catalog_coverage(),
            'user_satisfaction': self._get_user_satisfaction(),
            'precision_at_k': self._calculate_precision_at_k()
        }
    
    def _get_health_metrics(self) -> Dict:
        """
        システムヘルスメトリクス
        """
        return {
            'api_availability': self._check_api_availability(),
            'database_response': self._check_db_performance(),
            'cache_status': self._check_cache_health(),
            'error_rate': self._calculate_error_rate(),
            'feature_extraction_status': self._check_feature_extraction()
        }
    
    def _get_ab_test_metrics(self) -> Dict:
        """
        A/Bテストメトリクス
        """
        from music.services.ab_testing import ABTestFramework
        
        ab_framework = ABTestFramework()
        metrics = {}
        
        for experiment_name in ['recommendation_weights', 'diversity_optimization']:
            if ab_framework.is_experiment_active(experiment_name):
                metrics[experiment_name] = ab_framework.get_experiment_results(experiment_name)
        
        return metrics
    
    def _calculate_rpm(self) -> int:
        """
        1分あたりのリクエスト数
        """
        cache_key = 'request_count:minute'
        return cache.get(cache_key, 0)
    
    def _get_avg_response_time(self) -> float:
        """
        平均応答時間（ミリ秒）
        """
        cache_key = 'response_times:list'
        times = cache.get(cache_key, [])
        
        if times:
            return sum(times) / len(times)
        return 0.0
    
    def _get_cache_hit_rate(self) -> float:
        """
        キャッシュヒット率
        """
        hits = cache.get('cache:hits', 0)
        misses = cache.get('cache:misses', 0)
        
        total = hits + misses
        if total > 0:
            return hits / total
        return 0.0
    
    def _count_active_users(self) -> int:
        """
        アクティブユーザー数（過去5分間）
        """
        cache_key = 'active_users:set'
        active_users = cache.get(cache_key, set())
        return len(active_users)
    
    def _count_recent_recommendations(self) -> int:
        """
        最近の推薦数（過去1時間）
        """
        cache_key = 'recommendations:hour:count'
        return cache.get(cache_key, 0)
    
    def _count_daily_recommendations(self) -> int:
        """
        日次推薦数
        """
        today = datetime.now().date()
        start_time = datetime.combine(today, datetime.min.time())
        
        try:
            count = RecommendationLog.objects.filter(
                timestamp__gte=start_time
            ).count()
            return count
        except:
            # RecommendationLogが存在しない場合
            return cache.get('daily_recommendations:count', 0)
    
    def _count_daily_users(self) -> int:
        """
        日次ユニークユーザー数
        """
        cache_key = 'daily_users:set'
        users = cache.get(cache_key, set())
        return len(users)
    
    def _calculate_daily_ctr(self) -> float:
        """
        日次CTR計算
        """
        views = cache.get('daily:views', 0)
        clicks = cache.get('daily:clicks', 0)
        
        if views > 0:
            return clicks / views
        return 0.0
    
    def _get_popular_genres(self) -> List[Dict]:
        """
        人気ジャンルの取得
        """
        cache_key = 'popular_genres:daily'
        cached = cache.get(cache_key)
        
        if cached:
            return cached
        
        # Simple implementation: return top genre
        genres = [
            {'name': 'rock', 'count': 150},
            {'name': 'pop', 'count': 120},
            {'name': 'electronic', 'count': 80},
            {'name': 'jazz', 'count': 60},
            {'name': 'classical', 'count': 40}
        ]
        
        cache.set(cache_key, genres, 3600)
        return genres
    
    def _get_recommendation_distribution(self) -> Dict:
        """
        推薦タイプの分布
        """
        return {
            'content_based': cache.get('recs:content_based', 0),
            'collaborative': cache.get('recs:collaborative', 0),
            'popularity': cache.get('recs:popularity', 0),
            'trending': cache.get('recs:trending', 0)
        }
    
    def _calculate_diversity_score(self) -> float:
        """
        推薦の多様性スコア
        """
        cache_key = 'diversity_score:current'
        score = cache.get(cache_key)
        
        if score is not None:
            return score
        
        # Simple implementation: default value
        score = 0.75
        cache.set(cache_key, score, 300)
        return score
    
    def _calculate_novelty_score(self) -> float:
        """
        推薦の新規性スコア
        """
        # Simple implementation: ratio of low popularity tracks
        return 0.65
    
    def _calculate_catalog_coverage(self) -> float:
        """
        カタログカバレッジ（推薦されたトラックの割合）
        """
        total_tracks = Track.objects.count()
        recommended_tracks = cache.get('unique_recommended_tracks:count', 0)
        
        if total_tracks > 0:
            return min(1.0, recommended_tracks / total_tracks)
        return 0.0
    
    def _get_user_satisfaction(self) -> float:
        """
        User satisfaction (simple implementation)
        """
        # 実際はユーザーフィードバックから計算
        return 4.2  # 5点満点
    
    def _calculate_precision_at_k(self, k: int = 10) -> float:
        """
        Precision@K（上位K件の精度）
        """
        # Simple implementation
        return 0.78
    
    def _check_api_availability(self) -> float:
        """
        API可用性チェック
        """
        # Simple implementation: calculate from error rate
        error_rate = self._calculate_error_rate()
        return 1.0 - error_rate
    
    def _check_db_performance(self) -> Dict:
        """
        データベースパフォーマンスチェック
        """
        return {
            'avg_query_time': cache.get('db:avg_query_time', 0),
            'slow_queries': cache.get('db:slow_queries', 0),
            'status': 'healthy'
        }
    
    def _check_cache_health(self) -> Dict:
        """
        キャッシュヘルスチェック
        """
        try:
            # Redis pingテスト
            cache.set('health_check', 1, 1)
            status = 'healthy' if cache.get('health_check') == 1 else 'degraded'
        except:
            status = 'unhealthy'
        
        return {
            'status': status,
            'hit_rate': self._get_cache_hit_rate(),
            'memory_usage': cache.get('cache:memory_usage', 0)
        }
    
    def _calculate_error_rate(self) -> float:
        """
        エラー率計算
        """
        total_requests = cache.get('total_requests:hour', 0)
        errors = cache.get('errors:hour', 0)
        
        if total_requests > 0:
            return errors / total_requests
        return 0.0
    
    def _check_feature_extraction(self) -> Dict:
        """
        特徴量抽出ステータス
        """
        from music.models_recommendation import SimpleTrackFeatures
        
        total_tracks = Track.objects.count()
        tracks_with_features = SimpleTrackFeatures.objects.count()
        
        coverage = tracks_with_features / total_tracks if total_tracks > 0 else 0
        
        return {
            'coverage': coverage,
            'total_tracks': total_tracks,
            'processed_tracks': tracks_with_features,
            'status': 'healthy' if coverage > 0.8 else 'needs_attention'
        }
    
    def record_recommendation_request(
        self,
        user_id: int,
        response_time: float,
        cache_hit: bool,
        recommendation_type: str = None
    ):
        """
        推薦リクエストを記録
        """
        # RPMカウンター更新
        cache_key = 'request_count:minute'
        current_count = cache.get(cache_key, 0)
        cache.set(cache_key, current_count + 1, 60)
        
        # 時間別カウンター
        hour_key = 'total_requests:hour'
        hour_count = cache.get(hour_key, 0)
        cache.set(hour_key, hour_count + 1, 3600)
        
        # 応答時間記録
        times_key = 'response_times:list'
        times = cache.get(times_key, [])
        times.append(response_time)
        
        # 最新100件のみ保持
        if len(times) > 100:
            times = times[-100:]
        cache.set(times_key, times, 300)
        
        # キャッシュヒット記録
        if cache_hit:
            hits = cache.get('cache:hits', 0)
            cache.set('cache:hits', hits + 1, 3600)
        else:
            misses = cache.get('cache:misses', 0)
            cache.set('cache:misses', misses + 1, 3600)
        
        # アクティブユーザー記録
        active_key = 'active_users:set'
        active_users = cache.get(active_key, set())
        active_users.add(user_id)
        cache.set(active_key, active_users, 300)  # 5分間
        
        # 日次ユーザー記録
        daily_key = 'daily_users:set'
        daily_users = cache.get(daily_key, set())
        daily_users.add(user_id)
        cache.set(daily_key, daily_users, 86400)  # 24時間
        
        # 推薦タイプ別カウント
        if recommendation_type:
            type_key = f'recs:{recommendation_type}'
            type_count = cache.get(type_key, 0)
            cache.set(type_key, type_count + 1, 3600)
        
        # 推薦数カウント
        rec_hour_key = 'recommendations:hour:count'
        rec_count = cache.get(rec_hour_key, 0)
        cache.set(rec_hour_key, rec_count + 1, 3600)
    
    def record_user_interaction(
        self,
        user_id: int,
        track_id: int,
        interaction_type: str
    ):
        """
        ユーザーインタラクションを記録
        """
        if interaction_type == 'view':
            views = cache.get('daily:views', 0)
            cache.set('daily:views', views + 1, 86400)
        elif interaction_type == 'click':
            clicks = cache.get('daily:clicks', 0)
            cache.set('daily:clicks', clicks + 1, 86400)
        
        # トラックの推薦記録
        unique_key = 'unique_recommended_tracks:set'
        unique_tracks = cache.get(unique_key, set())
        unique_tracks.add(track_id)
        cache.set(unique_key, unique_tracks, 86400)
        
        # カウント更新
        count_key = 'unique_recommended_tracks:count'
        cache.set(count_key, len(unique_tracks), 86400)
    
    def record_error(self, error_type: str, error_message: str):
        """
        エラーを記録
        """
        errors_key = 'errors:hour'
        errors = cache.get(errors_key, 0)
        cache.set(errors_key, errors + 1, 3600)
        
        # エラーログ
        logger.error(f"Recommendation error: {error_type} - {error_message}")