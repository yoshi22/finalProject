import logging
from typing import List, Dict, Optional
from django.db import transaction
from django.core.cache import cache
from music.models import Track, Artist
from music.models_recommendation import SimpleTrackFeatures
# from music.lastfm import get_track_info, get_artist_info  # These functions need to be implemented
from music.utils.monitoring import PerformanceMonitor, ErrorTracker

logger = logging.getLogger("music")


class FeatureExtractor:
    """Extract and normalize features from tracks for content-based filtering."""
    
    @staticmethod
    def normalize_tempo(tempo: float) -> float:
        """Normalize tempo to 0-1 range (40-200 BPM)."""
        if tempo <= 0:
            return 0.5  # Default for unknown
        min_tempo, max_tempo = 40.0, 200.0
        return max(0.0, min(1.0, (tempo - min_tempo) / (max_tempo - min_tempo)))
    
    @staticmethod
    def normalize_popularity(popularity: int) -> float:
        """Normalize popularity score to 0-1 range."""
        if popularity <= 0:
            return 0.0
        return min(1.0, popularity / 100.0)
    
    @staticmethod
    @PerformanceMonitor.track_execution_time
    def extract_track_features(track: Track) -> Optional[SimpleTrackFeatures]:
        """
        Extract and create SimpleTrackFeatures for a track.
        
        Args:
            track: Track instance to process
            
        Returns:
            SimpleTrackFeatures instance or None if extraction fails
        """
        try:
            # Check if features already exist
            if hasattr(track, 'simple_features'):
                logger.debug(f"Features already exist for track: {track.id}")
                return track.simple_features
            
            # Get audio features from Track model
            energy = getattr(track, 'energy', 0.5)
            valence = getattr(track, 'valence', 0.5)
            tempo = getattr(track, 'tempo', 120.0)
            danceability = getattr(track, 'danceability', 0.5)
            acousticness = getattr(track, 'acousticness', 0.5)
            popularity = getattr(track, 'popularity', 50)
            
            # Normalize values
            tempo_normalized = FeatureExtractor.normalize_tempo(tempo)
            popularity_score = FeatureExtractor.normalize_popularity(popularity)
            
            # Get tags from Last.fm
            genre_tags, mood_tags = FeatureExtractor.fetch_tags_for_track(track)
            
            # Create SimpleTrackFeatures
            features = SimpleTrackFeatures.objects.create(
                track=track,
                energy=float(energy),
                valence=float(valence),
                tempo_normalized=tempo_normalized,
                danceability=float(danceability),
                acousticness=float(acousticness),
                popularity_score=popularity_score,
                genre_tags=genre_tags,
                mood_tags=mood_tags
            )
            
            logger.info(f"Extracted features for track: {track.id}")
            return features
            
        except Exception as e:
            ErrorTracker.log_error(
                "feature_extraction",
                str(e),
                {"track_id": track.id}
            )
            return None
    
    @staticmethod
    def fetch_tags_for_track(track: Track) -> tuple:
        """
        Fetch genre and mood tags from Last.fm.
        
        Returns:
            Tuple of (genre_tags, mood_tags)
        """
        genre_tags = []
        mood_tags = []
        
        # Cache key for tags
        cache_key = f"tags:track:{track.id}"
        cached_tags = cache.get(cache_key)
        
        if cached_tags:
            return cached_tags['genres'], cached_tags['moods']
        
        try:
            # Get track info from Last.fm (temporarily disabled - need to implement get_track_info)
            track_info = None  # get_track_info(track.name, track.artist.name)
            
            if track_info and 'toptags' in track_info:
                tags = track_info['toptags'].get('tag', [])
                
                # Categorize tags
                genre_keywords = ['rock', 'pop', 'jazz', 'classical', 'electronic', 
                                'metal', 'folk', 'blues', 'country', 'hip-hop', 
                                'rap', 'indie', 'alternative', 'punk', 'soul', 'r&b']
                
                for tag_info in tags[:10]:  # Top 10 tags
                    tag_name = tag_info['name'].lower()
                    
                    # Check if it's a genre tag
                    if any(keyword in tag_name for keyword in genre_keywords):
                        genre_tags.append(tag_name)
                    else:
                        mood_tags.append(tag_name)
            
            # Also get artist tags (temporarily disabled - need to implement get_artist_info)
            artist_info = None  # get_artist_info(track.artist.name)
            if artist_info and 'tags' in artist_info:
                artist_tags = artist_info['tags'].get('tag', [])
                for tag_info in artist_tags[:5]:  # Top 5 artist tags
                    tag_name = tag_info['name'].lower()
                    if tag_name not in genre_tags + mood_tags:
                        if any(keyword in tag_name for keyword in genre_keywords):
                            genre_tags.append(tag_name)
                        else:
                            mood_tags.append(tag_name)
            
            # Cache the tags
            cache.set(cache_key, {
                'genres': genre_tags[:5],  # Limit to top 5
                'moods': mood_tags[:5]
            }, timeout=86400)  # 24 hours
            
        except Exception as e:
            logger.warning(f"Failed to fetch tags for track {track.id}: {e}")
        
        return genre_tags[:5], mood_tags[:5]
    
    @staticmethod
    @PerformanceMonitor.track_execution_time
    def batch_extract_features(tracks: List[Track], batch_size: int = 50):
        """
        Extract features for multiple tracks in batches.
        
        Args:
            tracks: List of Track instances
            batch_size: Number of tracks to process at once
        """
        total = len(tracks)
        processed = 0
        failed = 0
        
        for i in range(0, total, batch_size):
            batch = tracks[i:i + batch_size]
            
            with transaction.atomic():
                for track in batch:
                    result = FeatureExtractor.extract_track_features(track)
                    if result:
                        processed += 1
                    else:
                        failed += 1
            
            logger.info(f"Batch progress: {processed + failed}/{total} "
                       f"(processed: {processed}, failed: {failed})")
        
        logger.info(f"Feature extraction complete: "
                   f"processed={processed}, failed={failed}")
        return processed, failed


class TagAnalyzer:
    """Analyze and process tags for similarity computation."""
    
    @staticmethod
    def get_tag_weights(tags: List[str]) -> Dict[str, float]:
        """
        Convert tags to weighted dictionary.
        Earlier tags have higher weights.
        """
        weights = {}
        for i, tag in enumerate(tags):
            # Weight decreases with position
            weight = 1.0 / (i + 1)
            weights[tag] = weight
        return weights
    
    @staticmethod
    def jaccard_similarity(tags1: List[str], tags2: List[str]) -> float:
        """
        Calculate Jaccard similarity between two tag lists.
        
        Returns:
            Similarity score between 0 and 1
        """
        if not tags1 or not tags2:
            return 0.0
        
        set1 = set(tags1)
        set2 = set(tags2)
        
        intersection = set1.intersection(set2)
        union = set1.union(set2)
        
        if not union:
            return 0.0
        
        return len(intersection) / len(union)
    
    @staticmethod
    def weighted_tag_similarity(tags1: List[str], tags2: List[str]) -> float:
        """
        Calculate weighted similarity between tag lists.
        Takes into account tag positions/importance.
        """
        if not tags1 or not tags2:
            return 0.0
        
        weights1 = TagAnalyzer.get_tag_weights(tags1)
        weights2 = TagAnalyzer.get_tag_weights(tags2)
        
        # Find common tags
        common_tags = set(weights1.keys()).intersection(set(weights2.keys()))
        
        if not common_tags:
            return 0.0
        
        # Calculate weighted similarity
        similarity = 0.0
        for tag in common_tags:
            similarity += min(weights1[tag], weights2[tag])
        
        # Normalize by maximum possible weight
        max_weight = min(
            sum(weights1.values()),
            sum(weights2.values())
        )
        
        if max_weight == 0:
            return 0.0
        
        return similarity / max_weight