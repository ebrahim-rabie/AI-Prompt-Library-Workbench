"""Application configuration classes (Design 3.3, NFR-02).

Pick one with the FLASK_CONFIG environment variable:
development (default), testing or production.
"""
import os
from datetime import timedelta
from pathlib import Path

# Repository root: src/app/config.py -> parents[2]
BASE_DIR = Path(__file__).resolve().parents[2]
INSTANCE_DIR = BASE_DIR / "instance"


def _database_url(default):
    # An empty DATABASE_URL= line in .env means "use the default", not an empty URL.
    url = os.environ.get("DATABASE_URL") or default
    # Some hosts still hand out the old "postgres://" scheme, which SQLAlchemy rejects.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


# Values that must never be used as a real SECRET_KEY (placeholders from docs and examples).
PLACEHOLDER_SECRET_KEYS = {"change-me", "changeme", "secret", "dev", "dev-only-insecure-key"}
MIN_PRODUCTION_SECRET_LENGTH = 32


class BaseConfig:
    # No hard-coded fallback: create_app() generates a random key for development
    # and refuses to start in production without a strong one.
    SECRET_KEY = os.environ.get("SECRET_KEY")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Reject request bodies over 1 MB (the largest real field is a 5,000-character template).
    MAX_CONTENT_LENGTH = 1024 * 1024

    # Sessions (FR-02): signed cookie, ended after 60 minutes without activity.
    SESSION_INACTIVITY_TIMEOUT = timedelta(minutes=60)
    PERMANENT_SESSION_LIFETIME = timedelta(minutes=60)
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # Lockout (FR-02): 5 wrong passwords in a row lock the account for 15 minutes.
    LOGIN_MAX_FAILED_ATTEMPTS = 5
    LOGIN_LOCK_DURATION = timedelta(minutes=15)

    # HTTPS (SRS 3.5.4): only enforced in production.
    FORCE_HTTPS = False

    WTF_CSRF_TIME_LIMIT = None


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    SQLALCHEMY_DATABASE_URI = _database_url(f"sqlite:///{(INSTANCE_DIR / 'dev.db').as_posix()}")


class TestingConfig(BaseConfig):
    TESTING = True
    SECRET_KEY = "test-secret-key"
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False


class ProductionConfig(BaseConfig):
    SQLALCHEMY_DATABASE_URI = _database_url(f"sqlite:///{(INSTANCE_DIR / 'prod.db').as_posix()}")
    SESSION_COOKIE_SECURE = True
    PREFERRED_URL_SCHEME = "https"
    FORCE_HTTPS = True


CONFIGS = {
    "development": DevelopmentConfig,
    "testing": TestingConfig,
    "production": ProductionConfig,
}
