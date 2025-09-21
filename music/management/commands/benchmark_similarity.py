from django.core.management.base import BaseCommand
from django.utils import timezone
import time
import statistics
import json

from music.models import Track
from music.models_recommendation import SimpleTrackFeatures
from music.services.similarity_engine import SimilarityEngine
from music.services.feature_extraction import FeatureExtractor
from music.services.cache_manager import CacheManager, CacheWarmer


class Command(BaseCommand):
    help = "Benchmark similarity calculation performance"

    def add_arguments(self, parser):
        parser.add_argument(
            '--num-tracks',
            type=int,
            default=100,
            help='Number of tracks to test'
        )
        parser.add_argument(
            '--num-iterations',
            type=int,
            default=10,
            help='Number of iterations for each benchmark'
        )
        parser.add_argument(
            '--warm-cache',
            action='store_true',
            help='Warm cache before benchmarking'
        )
        parser.add_argument(
            '--output-json',
            type=str,
            help='Output results to JSON file'
        )

    def handle(self, *args, **options):
        num_tracks = options['num_tracks']
        num_iterations = options['num_iterations']
        warm_cache = options['warm_cache']
        output_json = options['output_json']
        
        self.stdout.write(self.style.SUCCESS(
            f"Starting similarity engine benchmark with {num_tracks} tracks"
        ))
        
        # Get tracks with features
        tracks = list(Track.objects.filter(
            simple_features__isnull=False
        ).select_related('simple_features')[:num_tracks])
        
        if not tracks:
            self.stdout.write(self.style.ERROR(
                "No tracks with features found. Run feature extraction first."
            ))
            return
        
        self.stdout.write(f"Found {len(tracks)} tracks with features")
        
        # Warm cache if requested
        if warm_cache:
            self.stdout.write("Warming cache...")
            CacheWarmer.warm_popular_tracks(limit=min(50, num_tracks))
        
        results = {
            'metadata': {
                'num_tracks': len(tracks),
                'num_iterations': num_iterations,
                'cache_warmed': warm_cache,
                'timestamp': timezone.now().isoformat()
            },
            'benchmarks': {}
        }
        
        # Benchmark 1: Single similarity calculation
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("Benchmark 1: Single Similarity Calculation")
        self.stdout.write("=" * 50)
        
        times = []
        for _ in range(num_iterations):
            track_a = tracks[0]
            track_b = tracks[1]
            
            start = time.time()
            similarity = SimilarityEngine.calculate_track_similarity(track_a, track_b)
            elapsed = time.time() - start
            times.append(elapsed)
        
        results['benchmarks']['single_similarity'] = {
            'mean': statistics.mean(times),
            'median': statistics.median(times),
            'stdev': statistics.stdev(times) if len(times) > 1 else 0,
            'min': min(times),
            'max': max(times)
        }
        
        self.stdout.write(f"Mean: {statistics.mean(times)*1000:.2f}ms")
        self.stdout.write(f"Median: {statistics.median(times)*1000:.2f}ms")
        self.stdout.write(f"Min: {min(times)*1000:.2f}ms")
        self.stdout.write(f"Max: {max(times)*1000:.2f}ms")
        
        # Benchmark 2: Find similar tracks (with cache)
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("Benchmark 2: Find Similar Tracks (with cache)")
        self.stdout.write("=" * 50)
        
        times_cached = []
        times_uncached = []
        
        for i in range(num_iterations):
            track = tracks[i % len(tracks)]
            
            # Clear cache for this track
            cache_key = f"similar_tracks:{track.id}:20:0.5"
            CacheManager.delete(cache_key)
            
            # First call (cache miss)
            start = time.time()
            similar = SimilarityEngine.find_similar_tracks(track, limit=20)
            elapsed = time.time() - start
            times_uncached.append(elapsed)
            
            # Second call (cache hit)
            start = time.time()
            similar = SimilarityEngine.find_similar_tracks(track, limit=20)
            elapsed = time.time() - start
            times_cached.append(elapsed)
        
        results['benchmarks']['find_similar_uncached'] = {
            'mean': statistics.mean(times_uncached),
            'median': statistics.median(times_uncached),
            'stdev': statistics.stdev(times_uncached) if len(times_uncached) > 1 else 0,
            'min': min(times_uncached),
            'max': max(times_uncached)
        }
        
        results['benchmarks']['find_similar_cached'] = {
            'mean': statistics.mean(times_cached),
            'median': statistics.median(times_cached),
            'stdev': statistics.stdev(times_cached) if len(times_cached) > 1 else 0,
            'min': min(times_cached),
            'max': max(times_cached)
        }
        
        self.stdout.write("Uncached:")
        self.stdout.write(f"  Mean: {statistics.mean(times_uncached)*1000:.2f}ms")
        self.stdout.write(f"  Median: {statistics.median(times_uncached)*1000:.2f}ms")
        
        self.stdout.write("Cached:")
        self.stdout.write(f"  Mean: {statistics.mean(times_cached)*1000:.2f}ms")
        self.stdout.write(f"  Median: {statistics.median(times_cached)*1000:.2f}ms")
        
        cache_speedup = statistics.mean(times_uncached) / statistics.mean(times_cached)
        self.stdout.write(f"Cache speedup: {cache_speedup:.2f}x")
        results['benchmarks']['cache_speedup'] = cache_speedup
        
        # Benchmark 3: Batch similarity calculation
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("Benchmark 3: Batch Similarity Calculation")
        self.stdout.write("=" * 50)
        
        batch_sizes = [10, 50, 100]
        
        for batch_size in batch_sizes:
            if batch_size > len(tracks):
                continue
            
            times = []
            for _ in range(max(1, num_iterations // 2)):
                start = time.time()
                comparisons, stored = SimilarityEngine.precalculate_similarities(
                    tracks[:batch_size],
                    batch_size=batch_size,
                    min_similarity=0.3
                )
                elapsed = time.time() - start
                times.append(elapsed)
            
            mean_time = statistics.mean(times)
            comparisons_per_sec = comparisons / mean_time if mean_time > 0 else 0
            
            results['benchmarks'][f'batch_{batch_size}'] = {
                'mean_time': mean_time,
                'comparisons': comparisons,
                'comparisons_per_second': comparisons_per_sec
            }
            
            self.stdout.write(f"Batch size {batch_size}:")
            self.stdout.write(f"  Time: {mean_time:.2f}s")
            self.stdout.write(f"  Comparisons: {comparisons}")
            self.stdout.write(f"  Speed: {comparisons_per_sec:.2f} comparisons/sec")
        
        # Benchmark 4: Feature extraction
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write("Benchmark 4: Feature Extraction")
        self.stdout.write("=" * 50)
        
        # Find tracks without features
        tracks_without_features = Track.objects.filter(
            simple_features__isnull=True
        )[:10]
        
        if tracks_without_features:
            times = []
            for track in tracks_without_features:
                start = time.time()
                features = FeatureExtractor.extract_track_features(track)
                elapsed = time.time() - start
                times.append(elapsed)
                
                # Clean up
                if features:
                    features.delete()
            
            results['benchmarks']['feature_extraction'] = {
                'mean': statistics.mean(times),
                'median': statistics.median(times),
                'stdev': statistics.stdev(times) if len(times) > 1 else 0,
                'min': min(times),
                'max': max(times)
            }
            
            self.stdout.write(f"Mean: {statistics.mean(times)*1000:.2f}ms")
            self.stdout.write(f"Median: {statistics.median(times)*1000:.2f}ms")
        else:
            self.stdout.write("No tracks without features to test")
        
        # Summary
        self.stdout.write("\n" + "=" * 50)
        self.stdout.write(self.style.SUCCESS("BENCHMARK SUMMARY"))
        self.stdout.write("=" * 50)
        
        self.stdout.write(f"Tracks tested: {len(tracks)}")
        self.stdout.write(f"Iterations: {num_iterations}")
        
        if 'single_similarity' in results['benchmarks']:
            self.stdout.write(
                f"Single similarity: "
                f"{results['benchmarks']['single_similarity']['mean']*1000:.2f}ms"
            )
        
        if 'cache_speedup' in results['benchmarks']:
            self.stdout.write(f"Cache speedup: {results['benchmarks']['cache_speedup']:.2f}x")
        
        # Output JSON if requested
        if output_json:
            with open(output_json, 'w') as f:
                json.dump(results, f, indent=2)
            self.stdout.write(self.style.SUCCESS(
                f"Results saved to {output_json}"
            ))