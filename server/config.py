import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"


def _flag(name, default="0"):
    return os.environ.get(name, default).lower() in ("1", "true", "yes")


class Config:
    ENV_NAME = os.environ.get("YAHBS_ENV", "production")
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL") or (
        "sqlite:///" + str(INSTANCE_DIR / "yahbs.db")
    )
    UPLOAD_DIR = INSTANCE_DIR / "uploads"
    MAX_CONTENT_LENGTH = int(os.environ.get("MAX_UPLOAD_MB", "512")) * 1024 * 1024

    FORCE_HTTPS = _flag("FORCE_HTTPS", "0" if ENV_NAME == "development" else "1")
    PROXY_HOPS = int(os.environ.get("PROXY_HOPS", "0"))
    RATELIMIT_STORAGE_URI = os.environ.get("RATELIMIT_STORAGE_URI", "memory://")

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = FORCE_HTTPS
    SESSION_COOKIE_NAME = "yahbs_session"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    WTF_CSRF_TIME_LIMIT = 3600

    PLATFORMS = ("ps3", "ps4", "ps5")
    MAX_FAILED_LOGINS = 5
    LOCKOUT_MINUTES = 15
    APPS_PER_PAGE = 24
