# music/providers/base.py
from typing import Protocol, List, Dict

class TrackProvider(Protocol):
    """検索と詳細取得だけ定義しておくと、実装を自由に差し替え可能。"""
    def search(self, query: str, limit: int = 5) -> List[Dict]: ...
    def get(self, track_id: str) -> Dict: ...
