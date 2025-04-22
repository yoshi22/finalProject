import os, spotipy
from spotipy.oauth2 import SpotifyClientCredentials, SpotifyOAuth

# ── アプリ全体用（Client‑Credentials） ───────────────
APP = SpotifyClientCredentials(
    client_id     = os.getenv("SPOTIPY_CLIENT_ID"),
    client_secret = os.getenv("SPOTIPY_CLIENT_SECRET"),
)
def get_app_client():
    return spotipy.Spotify(auth_manager=APP)

# ── CLI でユーザートークンを取得 ─────────────────
def get_user_client_cli():
    oauth = SpotifyOAuth(
        client_id     = os.getenv("SPOTIPY_CLIENT_ID"),
        client_secret = os.getenv("SPOTIPY_CLIENT_SECRET"),
        redirect_uri  = os.getenv("SPOTIPY_REDIRECT_URI"),
        # 必要最小限のスコープだけ指定
        scope="user-read-private"
    )
    token = oauth.get_access_token(as_dict=False)
    return spotipy.Spotify(auth=token)
