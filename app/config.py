import os
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _split_csv(val: str | None):
    if not val:
        return []
    return [x.strip() for x in val.split(",") if x.strip()]


class Config:
    ENV = os.getenv("FLASK_ENV", "production")
    DEBUG = ENV != "production"
    TESTING = ENV == "test"

    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

    # Database
    DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///chatbot.db")
    SQLALCHEMY_DATABASE_URI = DATABASE_URL
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Redis
    REDIS_URL = os.getenv("REDIS_URL")

    # CORS
    CORS_ALLOWED_ORIGINS = _split_csv(os.getenv("CORS_ALLOWED_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000"))

    # Rate limiting
    DEFAULT_RATE_LIMIT_RPM = int(os.getenv("DEFAULT_RATE_LIMIT_RPM", "60"))

    # API key hash algorithm
    API_KEY_HASH_ALGO = os.getenv("API_KEY_HASH_ALGO", "bcrypt")

    # Dev convenience: auto create tables on startup for SQLite
    AUTO_CREATE_DB = os.getenv("AUTO_CREATE_DB", "true").lower() in ("1", "true", "yes")

    # Bootstrap on first run (for production envs too, gated by flag)
    AUTO_BOOTSTRAP = os.getenv("AUTO_BOOTSTRAP", "true").lower() in ("1", "true", "yes")
    SITE_TENANT_NAME = os.getenv("SITE_TENANT_NAME", "demo")
    SITE_API_KEY = os.getenv("SITE_API_KEY", "demo_key")
    BOOTSTRAP_SAMPLE_DATA = os.getenv("BOOTSTRAP_SAMPLE_DATA", "true").lower() in ("1", "true", "yes")
