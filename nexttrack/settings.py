"""
Django settings for nexttrack project (playlist + YouTube-embed edition)
Adapted for Render free-tier deployment
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")  # read .env locally

# -------------------------------------------------------------------
# Security
# -------------------------------------------------------------------
SECRET_KEY = os.getenv("DJANGO_SECRET", "CHANGE_ME_FOR_PRODUCTION")
DEBUG = os.getenv("DJANGO_DEBUG", "False") == "True"

# Accept any host unless explicitly limited (Render assigns a random sub-domain)
raw_hosts = os.getenv("DJANGO_ALLOWED_HOSTS", "*")
ALLOWED_HOSTS = [h.strip() for h in raw_hosts.split(",") if h.strip()]

# -------------------------------------------------------------------
# Installed apps
# -------------------------------------------------------------------
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.humanize",
    "music",
]

# -------------------------------------------------------------------
# Middleware / URL routing
# -------------------------------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",  # static file service
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "nexttrack.urls"

# -------------------------------------------------------------------
# Templates
# -------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "builtins": ["django.templatetags.static"],
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "nexttrack.wsgi.application"

# -------------------------------------------------------------------
# Database
# -------------------------------------------------------------------
# If DATABASE_URL env var is present (e.g. Render Postgres) prefer it
try:
    import dj_database_url

    DATABASES = {
        "default": dj_database_url.parse(
            os.getenv("DATABASE_URL"), conn_max_age=600, ssl_require=False
        )
        if os.getenv("DATABASE_URL")
        else {
            "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
            "NAME": os.getenv("DB_NAME", BASE_DIR / "db.sqlite3"),
        }
    }
except ImportError:
    # Fallback when dj_database_url is absent (local dev)
    DATABASES = {
        "default": {
            "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
            "NAME": os.getenv("DB_NAME", BASE_DIR / "db.sqlite3"),
        }
    }

# -------------------------------------------------------------------
# Internationalisation / Time-zone
# -------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_TZ = True

# -------------------------------------------------------------------
# Static / Media
# -------------------------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise compresses & fingerprints static files for production
STATICFILES_STORAGE = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
)

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# -------------------------------------------------------------------
# Cache (loc-mem by default, Redis if REDIS_URL set)
# -------------------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "nexttrack-cache",
    }
}

# -------------------------------------------------------------------
# Logging
# -------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {
        "handlers": ["console"],
        "level": os.getenv("DJANGO_LOG_LEVEL", "INFO"),
    },
}

# -------------------------------------------------------------------
# External API keys & endpoints
# -------------------------------------------------------------------
# Last.fm
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY", "")
LASTFM_ROOT = "http://ws.audioscrobbler.com/2.0/"
LASTFM_USER_AGENT = "NextTrackStudent/1.0"

# (Optional) YouTube – still used for fallback search links
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

GETSONGBPM_KEY = os.getenv("GETSONGBPM_KEY", "")

# Deezer (preview / artwork)
DEEZER_ROOT = os.getenv("DEEZER_ROOT", "https://api.deezer.com")

# MusicStax (audio-features replacement for Spotify)
MUSICSTAX_ROOT = os.getenv("MUSICSTAX_ROOT", "https://musicstax.com/api")
MUSICSTAX_KEY = os.getenv("MUSICSTAX_KEY", "")  # ←必須: dashboard で取得したキー

# -------------------------------------------------------------------
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -------------------------------------------------------------------
# Auth redirect URLs
# -------------------------------------------------------------------
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# -------------------------------------------------------------------
# Security headers when deployed behind TLS proxy
# -------------------------------------------------------------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

# -------------------------------------------------------------------
# Redis cache override (if REDIS_URL provided)
# -------------------------------------------------------------------
if os.getenv("REDIS_URL"):
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": os.getenv("REDIS_URL"),
            "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient"},
            "TIMEOUT": 60 * 60,  # 1 hour
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
            "LOCATION": "nexttrack-cache",
            "TIMEOUT": 60 * 10,  # 10 minutes
        }
    }

# --- GetSongBPM ----------------------------------------------------
GETSONGBPM_KEY = os.getenv("GETSONGBPM_KEY", "")
