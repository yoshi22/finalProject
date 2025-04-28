import logging, requests, urllib.parse
from django.conf import settings

def youtube_id(query: str) -> str | None:
    """
    Try to return the first YouTube video ID that matches the query.
    If the API key is missing or any error occurs, return None so that
    the caller can fall back to a normal /results search page.
    """
    if not settings.YOUTUBE_API_KEY:
        logging.info("YOUTUBE_API_KEY not set – youtube_id() will skip API call.")
        return None

    try:
        res = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "key": settings.YOUTUBE_API_KEY,
                "part": "snippet",
                "type": "video",
                "videoCategoryId": "10",
                "maxResults": 1,
                "q": query,
            },
            timeout=5,
        )
        res.raise_for_status()
        items = res.json().get("items")
        if items:
            return items[0]["id"]["videoId"]
    except Exception as exc:
        logging.warning("YouTube search failed: %s", exc)

    # return None → caller will construct a /results link
    return None
