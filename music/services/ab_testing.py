import hashlib
import json
from typing import Dict, Any, Optional
from datetime import datetime, timedelta
from django.core.cache import cache
from django.contrib.auth import get_user_model
import logging

logger = logging.getLogger(__name__)
User = get_user_model()


class ABTestFramework:
    """
    A/Bテスト管理フレームワーク
    """
    
    def __init__(self):
        self.experiments = {}
        self._load_experiments()
    
    def _load_experiments(self):
        """
        実験設定をロード
        """
        self.experiments = {
            'recommendation_weights': {
                'name': 'Recommendation Weight Optimization',
                'status': 'active',
                'start_date': datetime(2025, 8, 1),
                'end_date': datetime(2025, 9, 30),
                'variants': {
                    'control': {
                        'allocation': 0.5,
                        'config': {
                            'content_weight': 0.4,
                            'collaborative_weight': 0.3,
                            'popularity_weight': 0.2,
                            'trending_weight': 0.1
                        }
                    },
                    'variant_a': {
                        'allocation': 0.25,
                        'config': {
                            'content_weight': 0.5,
                            'collaborative_weight': 0.3,
                            'popularity_weight': 0.15,
                            'trending_weight': 0.05
                        }
                    },
                    'variant_b': {
                        'allocation': 0.25,
                        'config': {
                            'content_weight': 0.3,
                            'collaborative_weight': 0.4,
                            'popularity_weight': 0.2,
                            'trending_weight': 0.1
                        }
                    }
                }
            },
            'diversity_optimization': {
                'name': 'Diversity Factor Testing',
                'status': 'active',
                'start_date': datetime(2025, 8, 15),
                'end_date': datetime(2025, 10, 15),
                'variants': {
                    'low_diversity': {
                        'allocation': 0.33,
                        'config': {'diversity_factor': 0.1}
                    },
                    'medium_diversity': {
                        'allocation': 0.34,
                        'config': {'diversity_factor': 0.3}
                    },
                    'high_diversity': {
                        'allocation': 0.33,
                        'config': {'diversity_factor': 0.5}
                    }
                }
            }
        }
    
    def get_user_variant(
        self, 
        user: User, 
        experiment_name: str
    ) -> Optional[str]:
        """
        ユーザーの実験グループを取得
        """
        experiment = self.experiments.get(experiment_name)
        if not experiment:
            return None
        
        # 実験がアクティブか確認
        if experiment['status'] != 'active':
            return None
        
        # 日付範囲確認
        now = datetime.now()
        if now < experiment['start_date'] or now > experiment['end_date']:
            return None
        
        # ユーザーグループをキャッシュから取得
        cache_key = f"ab_test:{experiment_name}:{user.id}"
        variant = cache.get(cache_key)
        
        if variant:
            return variant
        
        # 新規割り当て
        variant = self._assign_variant(user, experiment)
        
        # キャッシュに保存（実験期間中）
        ttl = (experiment['end_date'] - now).total_seconds()
        cache.set(cache_key, variant, ttl)
        
        # イベント記録
        self._log_assignment(user, experiment_name, variant)
        
        return variant
    
    def _assign_variant(self, user: User, experiment: Dict) -> str:
        """
        ユーザーを実験グループに割り当て
        """
        # ユーザーIDのハッシュ値を計算
        user_hash = hashlib.md5(
            f"{experiment['name']}:{user.id}".encode()
        ).hexdigest()
        
        # 0-1の値に変換
        hash_value = int(user_hash[:8], 16) / (16**8)
        
        # 割り当て率に基づいてグループ決定
        cumulative = 0
        for variant_name, variant_config in experiment['variants'].items():
            cumulative += variant_config['allocation']
            if hash_value < cumulative:
                return variant_name
        
        # フォールバック（通常到達しない）
        return list(experiment['variants'].keys())[0]
    
    def get_variant_config(
        self, 
        user: User, 
        experiment_name: str
    ) -> Dict[str, Any]:
        """
        ユーザーの実験設定を取得
        """
        variant = self.get_user_variant(user, experiment_name)
        
        if not variant:
            return {}
        
        experiment = self.experiments[experiment_name]
        return experiment['variants'][variant].get('config', {})
    
    def track_event(
        self,
        user: User,
        experiment_name: str,
        event_type: str,
        event_data: Optional[Dict] = None
    ):
        """
        実験イベントを記録
        """
        variant = self.get_user_variant(user, experiment_name)
        
        if not variant:
            return
        
        event = {
            'experiment': experiment_name,
            'variant': variant,
            'user_id': user.id,
            'event_type': event_type,
            'event_data': event_data or {},
            'timestamp': datetime.now().isoformat()
        }
        
        # イベントをログに記録（実際はデータベースや分析ツールに送信）
        logger.info(f"A/B Test Event: {json.dumps(event)}")
        
        # Update metrics (simple implementation)
        self._update_metrics(experiment_name, variant, event_type)
    
    def _update_metrics(
        self,
        experiment_name: str,
        variant: str,
        event_type: str
    ):
        """
        実験メトリクスを更新
        """
        cache_key = f"ab_metrics:{experiment_name}:{variant}:{event_type}"
        
        # 現在のカウントを取得
        current_count = cache.get(cache_key, 0)
        
        # インクリメント
        cache.set(cache_key, current_count + 1, 60 * 60 * 24)  # 24時間
    
    def _log_assignment(
        self,
        user: User,
        experiment_name: str,
        variant: str
    ):
        """
        グループ割り当てを記録
        """
        logger.info(
            f"User {user.id} assigned to {variant} "
            f"in experiment {experiment_name}"
        )
    
    def get_experiment_results(
        self, 
        experiment_name: str
    ) -> Dict[str, Any]:
        """
        実験結果を取得
        """
        experiment = self.experiments.get(experiment_name)
        if not experiment:
            return {}
        
        results = {
            'experiment': experiment_name,
            'status': experiment['status'],
            'variants': {}
        }
        
        # 各バリアントのメトリクスを集計
        for variant_name in experiment['variants']:
            metrics = {}
            
            # イベントタイプごとのカウントを取得
            for event_type in ['view', 'click', 'play', 'like']:
                cache_key = f"ab_metrics:{experiment_name}:{variant_name}:{event_type}"
                count = cache.get(cache_key, 0)
                metrics[event_type] = count
            
            # CTR計算
            if metrics['view'] > 0:
                metrics['ctr'] = metrics['click'] / metrics['view']
            else:
                metrics['ctr'] = 0
            
            results['variants'][variant_name] = metrics
        
        return results
    
    def is_experiment_active(self, experiment_name: str) -> bool:
        """
        実験がアクティブかチェック
        """
        experiment = self.experiments.get(experiment_name)
        if not experiment:
            return False
        
        if experiment['status'] != 'active':
            return False
        
        now = datetime.now()
        return experiment['start_date'] <= now <= experiment['end_date']