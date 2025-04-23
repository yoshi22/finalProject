"""
nexttrack/settings.py  ―  Django 5.2 sample settings
-----------------------------------------------------

環境変数（.env）を優先して読み込み、
デフォルト値でフォールバックする構成です。
"""

from pathlib import Path
import os
from dotenv import load_dotenv   # python-dotenv をインストール済み前提

# --------------------------------------------------
# ベースディレクトリ
# --------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent

# .env 読み込み (.env は BASE_DIR 直下想定)
load_dotenv(BASE_DIR / ".env")

# --------------------------------------------------
# セキュリティ
# --------------------------------------------------
SECRET_KEY = os.getenv("DJANGO_SECRET", "!!!_DEVELOPMENT_ONLY_SECRET_!!!")
DEBUG = os.getenv("DJANGO_DEBUG", "True") == "True"
ALLOWED_HOSTS = os.getenv("DJANGO_ALLOWED_HOSTS", "").split(",") if not DEBUG else []

# --------------------------------------------------
# アプリケーション
# --------------------------------------------------
INSTALLED_APPS = [
    # 標準
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # サードパーティがあればここに追記（例: rest_framework）
    # 自作アプリ
    "django.contrib.humanize",  # 人間向けのフォーマッタ
    "music",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "nexttrack.urls"

# --------------------------------------------------
# テンプレート
# --------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],   # プロジェクト共通テンプレート
        "APP_DIRS": True,                   # app/templates も自動読込
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --------------------------------------------------
# WSGI / ASGI
# --------------------------------------------------
WSGI_APPLICATION = "nexttrack.wsgi.application"
# ASGI_APPLICATION = "nexttrack.asgi.application"  # async を使う場合はこちら

# --------------------------------------------------
# データベース（開発は SQLite、必要なら .env で上書き）
# --------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
        "NAME": os.getenv("DB_NAME", BASE_DIR / "db.sqlite3"),
        "USER": os.getenv("DB_USER", ""),
        "PASSWORD": os.getenv("DB_PASSWORD", ""),
        "HOST": os.getenv("DB_HOST", ""),
        "PORT": os.getenv("DB_PORT", ""),
    }
}

# --------------------------------------------------
# パスワード検証
# --------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

# --------------------------------------------------
# 国際化
# --------------------------------------------------
LANGUAGE_CODE = "ja"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_TZ = True

# --------------------------------------------------
# 静的 / メディアファイル
# --------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"      # collectstatic 先（本番用）

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"             # ユーザアップロード

# --------------------------------------------------
# キャッシュ（開発はローカルメモリ、本番は memcached / redis 推奨）
# --------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "nexttrack-cache",
    }
}

# --------------------------------------------------
# ロギング（最低限：コンソール出力）
# --------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
    },
}

# --------------------------------------------------
# Last.fm API 連携用カスタム設定
# --------------------------------------------------
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY", "")
LASTFM_ROOT    = "http://ws.audioscrobbler.com/2.0/"
LASTFM_USER_AGENT = "NextTrackStudent/1.0"   # 共通ヘッダで送ると親切

# --------------------------------------------------
# 追加セキュリティ（HTTPS を強制する場合）
# --------------------------------------------------
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# --------------------------------------------------
# デフォルトの AutoField 型
# --------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
