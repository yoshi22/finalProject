import logging, requests
from django.conf import settings

def youtube_id(query: str) -> str | None:
    """
    Return videoId of the first Music-category result that matches 'Artist Track'.
    """
    try:
        res = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "key": settings.YOUTUBE_API_KEY,
                "part": "snippet",
                "type": "video",
                "videoCategoryId": "10",   # Music
                "maxResults": 1,
                "q": query,
            },
            timeout=5,
        )
        return res.json()["items"][0]["id"]["videoId"]
    except Exception as exc:
        logging.warning("YouTube search failed: %s", exc)
        return None
