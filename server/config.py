import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
INSTANCE_DIR = BASE_DIR / "instance"


def _load_dotenv(path):
    """Minimal .env reader (no dependency). Real environment variables win; empty values are ignored."""
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return
    for line in lines:
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key, val = key.strip(), val.strip()
        if len(val) >= 2 and val[0] == val[-1] and val[0] in "\"'":
            val = val[1:-1]
        if key and val:
            os.environ.setdefault(key, val)


_load_dotenv(BASE_DIR / ".env")


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

    # Used to build links in emails (do NOT trust the Host header for this). e.g. https://store.example.com
    PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "")
    MAIL_SERVER = os.environ.get("MAIL_SERVER", "")        # empty => emails are only logged (dev)
    MAIL_PORT = int(os.environ.get("MAIL_PORT", "587"))
    MAIL_USERNAME = os.environ.get("MAIL_USERNAME", "")
    MAIL_PASSWORD = os.environ.get("MAIL_PASSWORD", "")
    MAIL_FROM = os.environ.get("MAIL_FROM", "noreply@localhost")
    # Catalog signing: 32-byte Ed25519 seed as 64 hex chars (generate: flask --app app gen-signing-key)
    SIGNING_KEY_HEX = os.environ.get("SIGNING_KEY_HEX", "")
    # ClamAV daemon, "host:port" or a unix socket path. Empty = scanning disabled. Fails closed if set.
    CLAMD_ADDR = os.environ.get("CLAMD_ADDR", "")
    REQUIRE_EMAIL_VERIFY = _flag("REQUIRE_EMAIL_VERIFY", "0" if ENV_NAME == "development" else "1")
    PUBLIC_URL = os.environ.get("PUBLIC_URL", "")  # e.g. https://store.example.com (used in emails)
    PLATFORMS = ("ps3", "ps4", "ps5")
    MAX_FAILED_LOGINS = 5
    LOCKOUT_MINUTES = 15
    APPS_PER_PAGE = 24
