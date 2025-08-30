from __future__ import annotations

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate

db = SQLAlchemy()
migrate = Migrate()

redis_client = None


def init_redis(app: Flask):
    global redis_client
    url = app.config.get("REDIS_URL")
    if not url:
        redis_client = None
        return None
    try:
        import redis  # type: ignore

        redis_client = redis.from_url(url)
        # smoke ping
        try:
            redis_client.ping()
        except Exception:
            # allow app to run without redis
            redis_client = None
    except Exception:
        redis_client = None
    return redis_client

