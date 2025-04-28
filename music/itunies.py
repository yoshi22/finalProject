# music/itunes.py  ★新規ファイル
import logging
import requests
import urllib.parse

def itunes_preview(term: str) -> str | None:
    """
    iTunes Search API から 30-sec preview URL を取得して返す。
    取得できない場合は None を返す。
    """
    try:
        res = requests.get(
            "https://itunes.apple.com/search",
            params={
                "term": term,
                "media": "music",
                "entity": "song",
                "limit": 1,
            },
            timeout=5,
        )
        res.raise_for_status()
        js = res.json()
        if js.get("resultCount"):
            return js["results"][0].get("previewUrl")
    except Exception as exc:
        logging.warning("iTunes preview failed: %s", exc)

    # 失敗時は検索結果ページ (ブラウザにまかせる) を返す
    q = urllib.parse.quote_plus(term)
    return f"https://music.apple.com/jp/search?term={q}"
