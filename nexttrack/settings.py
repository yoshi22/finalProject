"""
Django settings for nexttrack project (playlist + YouTube-embed edition)
Adapted for Render free tier deployment
"""

from pathlib import Path
import os
from dotenv import load_dotenv

# -------------------------------------------------------------------
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")                 # read .env locally

# -- security --------------------------------------------------------
SECRET_KEY = os.getenv("DJANGO_SECRET", "CHANGE_ME_FOR_PRODUCTION")
DEBUG = os.getenv("DJANGO_DEBUG", "False") == "True"

# Accept any host unless explicitly limited (Render assigns a random sub-domain)
raw_hosts = os.getenv("DJANGO_ALLOWED_HOSTS", "*")
ALLOWED_HOSTS = [h.strip() for h in raw_hosts.split(",") if h.strip()]

# -- apps ------------------------------------------------------------
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

# -- middleware / URL -----------------------------------------------
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",        # ★ add
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "nexttrack.urls"

# -- templates -------------------------------------------------------
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

# -- database --------------------------------------------------------
# If DATABASE_URL env var is present (Render Postgres等)、それを優先
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
    # dj_database_url が入っていない開発環境でも動く fallback
    DATABASES = {
        "default": {
            "ENGINE": os.getenv("DB_ENGINE", "django.db.backends.sqlite3"),
            "NAME": os.getenv("DB_NAME", BASE_DIR / "db.sqlite3"),
        }
    }

# -- i18n / tz -------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Tokyo"
USE_I18N = True
USE_TZ = True

# -- static / media --------------------------------------------------
STATIC_URL = "/static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

# WhiteNoise will compress & fingerprint files for production
STATICFILES_STORAGE = (
    "whitenoise.storage.CompressedManifestStaticFilesStorage"
)

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# -- cache -----------------------------------------------------------
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "nexttrack-cache",
    }
}

# -- logging ---------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {"console": {"class": "logging.StreamHandler"}},
    "root": {"handlers": ["console"], "level": os.getenv("DJANGO_LOG_LEVEL", "INFO")},
}

# -- external API keys ----------------------------------------------
LASTFM_API_KEY = os.getenv("LASTFM_API_KEY", "")
LASTFM_ROOT = "http://ws.audioscrobbler.com/2.0/"
LASTFM_USER_AGENT = "NextTrackStudent/1.0"

YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY", "")

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# -- auth redirect ---------------------------------------------------
LOGIN_REDIRECT_URL = "/"
LOGOUT_REDIRECT_URL = "/"

# -- security headers when deployed behind TLS proxy ----------------
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
