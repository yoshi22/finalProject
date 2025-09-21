# music/providers/base.py
from typing import Protocol, List, Dict

class TrackProvider(Protocol):
    """Define search and detail retrieval for flexible implementation replacement."""
    def search(self, query: str, limit: int = 5) -> List[Dict]: ...
    def get(self, track_id: str) -> Dict: ...
