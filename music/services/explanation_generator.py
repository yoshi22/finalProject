"""
Recommendation Explanation Generator
Natural language explanation for music recommendations
"""

from typing import Dict, List, Optional
import random
from music.models import Track
from music.services.deepcut_engine import DeepCutCandidate
from music.models_recommendation import SimpleTrackFeatures
import logging

logger = logging.getLogger(__name__)


class ExplanationGenerator:
    """
    Generate natural language explanations for recommendations
    Template-based generation for easy-to-understand descriptions
    """
    
    def __init__(self):
        self.templates = {
            'high_similarity': [
                "This track shares {similarity_percent}% musical similarity with {seed_track}",
                "Musically very close to {seed_track} with {common_elements}",
                "If you enjoy {seed_track}, this has a similar {main_feature}",
                "Strong musical connection to {seed_track} ({similarity_percent}% match)"
            ],
            'hidden_gem': [
                "A hidden gem with only {playcount:,} plays, waiting to be discovered",
                "An underappreciated track that deserves more attention ({playcount:,} plays)",
                "Rarely heard but highly relevant to your taste",
                "Underground favorite with just {playcount:,} listeners"
            ],
            'genre_match': [
                "Shares the {common_genres} genres you seem to enjoy",
                "Perfect match for fans of {genre_list}",
                "Combines {genre1} with {genre2} in a unique way",
                "Fits perfectly in the {main_genre} category"
            ],
            'tempo_match': [
                "Similar energy level with {tempo} BPM",
                "Matching tempo makes this perfect for the same mood ({tempo} BPM)",
                "Same rhythmic feel at {tempo} BPM",
                "Energy matches at {tempo} BPM"
            ],
            'artist_discovery': [
                "Discover {artist_name}, an artist you haven't heard before",
                "From {artist_name}, who creates similar music to your favorites",
                "Expand your horizons with {artist_name}",
                "New artist alert: {artist_name} makes music you'll love"
            ],
            'novelty': [
                "Something different yet complementary to your usual taste",
                "A fresh take on the {genre} sound you enjoy",
                "Explores new territory while staying true to {element}",
                "Unique blend that expands your musical palette"
            ],
            'exploration': [
                "Deep dive discovery at {exploration_percent}% exploration level",
                "Found in the depths of the music catalog for adventurous listeners",
                "Rare find for those willing to explore",
                "Off the beaten path but worth the journey"
            ]
        }
    
    def generate_explanation(
        self,
        candidate: DeepCutCandidate,
        seed_track: Track,
        user_context: Optional[Dict] = None
    ) -> str:
        """
        Generate recommendation explanation
        
        Args:
            candidate: Deep-cut候補
            seed_track: シードトラック
            user_context: ユーザーコンテキスト（オプション）
        
        Returns:
            説明文
        """
        try:
            explanations = []
            
            # 類似度に基づく説明
            if candidate.similarity_score > 0.7:
                explanation = self._generate_similarity_explanation(
                    candidate, seed_track
                )
                if explanation:
                    explanations.append(explanation)
            
            # 隠れた名曲としての説明
            if candidate.popularity_score > 0.7:
                explanation = self._generate_hidden_gem_explanation(candidate)
                if explanation:
                    explanations.append(explanation)
            
            # ジャンルマッチの説明
            genre_explanation = self._generate_genre_explanation(
                candidate, seed_track
            )
            if genre_explanation:
                explanations.append(genre_explanation)
            
            # 新規性の説明
            if candidate.novelty_score > 0.6:
                explanation = self._generate_novelty_explanation(
                    candidate, seed_track
                )
                if explanation:
                    explanations.append(explanation)
            
            # 探索レベルに基づく説明
            if 'exploration_level' in candidate.explanation_factors.get('weights', {}):
                exploration_explanation = self._generate_exploration_explanation(
                    candidate
                )
                if exploration_explanation:
                    explanations.append(exploration_explanation)
            
            # 説明を結合
            if not explanations:
                explanations.append(self._generate_default_explanation(candidate))
            
            # 最大2つの説明を選択
            selected_explanations = explanations[:2]
            return " • ".join(selected_explanations)
            
        except Exception as e:
            logger.error(f"Error generating explanation: {e}")
            return self._generate_default_explanation(candidate)
    
    def _generate_similarity_explanation(
        self,
        candidate: DeepCutCandidate,
        seed_track: Track
    ) -> str:
        """
        Generate similarity-based explanation
        """
        try:
            similarity_percent = int(candidate.similarity_score * 100)
            
            # 共通要素を特定
            common_elements = self._identify_common_elements(
                candidate.track, seed_track
            )
            
            # テンプレートをランダムに選択
            template = random.choice(self.templates['high_similarity'])
            
            # 主要な特徴を取得
            main_feature = common_elements.split(',')[0] if common_elements else "style"
            
            return template.format(
                similarity_percent=similarity_percent,
                seed_track=seed_track.title,
                common_elements=common_elements,
                main_feature=main_feature
            )
        except Exception as e:
            logger.error(f"Error in similarity explanation: {e}")
            return ""
    
    def _generate_hidden_gem_explanation(
        self,
        candidate: DeepCutCandidate
    ) -> str:
        """
        Generate hidden gem explanation
        """
        try:
            playcount = candidate.track.playcount or 0
            
            if playcount < 1000:
                template = self.templates['hidden_gem'][0]
            elif playcount < 10000:
                template = random.choice(self.templates['hidden_gem'][:2])
            else:
                template = self.templates['hidden_gem'][2]
            
            return template.format(playcount=playcount)
        except Exception as e:
            logger.error(f"Error in hidden gem explanation: {e}")
            return ""
    
    def _generate_genre_explanation(
        self,
        candidate: DeepCutCandidate,
        seed_track: Track
    ) -> Optional[str]:
        """
        Generate genre match explanation
        """
        try:
            # 特徴量を取得
            candidate_features = None
            seed_features = None
            
            try:
                candidate_features = SimpleTrackFeatures.objects.get(track=candidate.track)
                seed_features = SimpleTrackFeatures.objects.get(track=seed_track)
            except SimpleTrackFeatures.DoesNotExist:
                return None
            
            if not candidate_features or not seed_features:
                return None
            
            candidate_genres = self._extract_genre_names(candidate_features)
            seed_genres = self._extract_genre_names(seed_features)
            
            if not candidate_genres or not seed_genres:
                return None
            
            common_genres = candidate_genres & seed_genres
            
            if common_genres:
                genre_list = ", ".join(list(common_genres)[:2])
                template = random.choice(self.templates['genre_match'][:2])
                return template.format(
                    common_genres=genre_list,
                    genre_list=genre_list
                )
            elif candidate_genres:
                # 異なるジャンルの組み合わせ
                genres = list(candidate_genres)[:2]
                if len(genres) >= 2:
                    template = self.templates['genre_match'][2]
                    return template.format(genre1=genres[0], genre2=genres[1])
                elif genres:
                    template = self.templates['genre_match'][3]
                    return template.format(main_genre=genres[0])
            
            return None
            
        except Exception as e:
            logger.error(f"Error in genre explanation: {e}")
            return None
    
    def _generate_novelty_explanation(
        self,
        candidate: DeepCutCandidate,
        seed_track: Track
    ) -> str:
        """
        Generate novelty explanation
        """
        try:
            template = random.choice(self.templates['novelty'])
            
            # ジャンル情報を取得
            genre = "music"
            element = "style"
            
            try:
                features = SimpleTrackFeatures.objects.get(track=candidate.track)
                if features.genre_tags:
                    if isinstance(features.genre_tags[0], dict):
                        genre = features.genre_tags[0].get('name', 'music')
                    else:
                        genre = str(features.genre_tags[0])
                    
                # 要素を特定
                if features.tempo:
                    element = "energy"
                elif features.key:
                    element = "harmony"
            except SimpleTrackFeatures.DoesNotExist:
                pass
            
            return template.format(genre=genre, element=element)
            
        except Exception as e:
            logger.error(f"Error in novelty explanation: {e}")
            return self.templates['novelty'][0]
    
    def _generate_exploration_explanation(
        self,
        candidate: DeepCutCandidate
    ) -> str:
        """
        Generate exploration level explanation
        """
        try:
            weights = candidate.explanation_factors.get('weights', {})
            exploration_level = weights.get('novelty', 0.5)
            exploration_percent = int(exploration_level * 100)
            
            template = random.choice(self.templates['exploration'])
            return template.format(exploration_percent=exploration_percent)
            
        except Exception as e:
            logger.error(f"Error in exploration explanation: {e}")
            return ""
    
    def _generate_default_explanation(
        self,
        candidate: DeepCutCandidate
    ) -> str:
        """
        Generate default explanation
        """
        return f"Recommended based on your interest in similar music"
    
    def _identify_common_elements(
        self,
        track1: Track,
        track2: Track
    ) -> str:
        """
        共通要素を特定
        """
        elements = []
        
        try:
            features1 = SimpleTrackFeatures.objects.get(track=track1)
            features2 = SimpleTrackFeatures.objects.get(track=track2)
            
            # テンポの類似性
            if (features1.tempo and features2.tempo and
                abs(features1.tempo - features2.tempo) < 10):
                elements.append("similar tempo")
            
            # キーの一致
            if features1.key and features2.key and features1.key == features2.key:
                elements.append(f"same key ({features1.key})")
            
            # エネルギーレベル
            if (features1.energy is not None and features2.energy is not None and
                abs(features1.energy - features2.energy) < 0.2):
                elements.append("similar energy")
            
            # 音響的特徴
            if (features1.acousticness is not None and features2.acousticness is not None and
                abs(features1.acousticness - features2.acousticness) < 0.2):
                if features1.acousticness > 0.5:
                    elements.append("acoustic feel")
                else:
                    elements.append("electronic sound")
                    
        except SimpleTrackFeatures.DoesNotExist:
            pass
        except Exception as e:
            logger.error(f"Error identifying common elements: {e}")
        
        if not elements:
            elements.append("similar style")
        
        return ", ".join(elements[:3])  # 最大3要素
    
    def _extract_genre_names(self, features: SimpleTrackFeatures) -> set:
        """
        特徴量からジャンル名を抽出
        """
        genres = set()
        
        if features.genre_tags:
            for tag in features.genre_tags:
                if isinstance(tag, dict):
                    genre_name = tag.get('name', '')
                    if genre_name:
                        genres.add(genre_name)
                elif isinstance(tag, str):
                    genres.add(tag)
        
        return genres
    
    def generate_batch_explanations(
        self,
        candidates: List[DeepCutCandidate],
        seed_track: Track,
        user_context: Optional[Dict] = None
    ) -> Dict[int, str]:
        """
        Generate explanations in batch
        
        Args:
            candidates: Deep-cut候補リスト
            seed_track: シードトラック
            user_context: ユーザーコンテキスト
        
        Returns:
            トラックIDと説明文の辞書
        """
        explanations = {}
        
        for candidate in candidates:
            try:
                explanation = self.generate_explanation(
                    candidate,
                    seed_track,
                    user_context
                )
                explanations[candidate.track.id] = explanation
            except Exception as e:
                logger.error(f"Error generating explanation for track {candidate.track.id}: {e}")
                explanations[candidate.track.id] = self._generate_default_explanation(candidate)
        
        return explanations