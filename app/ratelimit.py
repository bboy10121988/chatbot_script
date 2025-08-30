from __future__ import annotations

import time
from dataclasses import dataclass
from flask import g, current_app

from .extensions import redis_client


@dataclass
class RateLimit:
    limit: int
    remaining: int
    reset: int


def _key(prefix: str, api_key: str):
    return f"rl:{prefix}:{api_key}"


def check_rate_limit(scope: str = "default", rpm: int | None = None) -> RateLimit:
    api_key = getattr(g, "api_key", None)
    if not api_key:
        # if no api key, treat as strict
        api_key = "anon"
    limit = rpm or getattr(g, "rate_limit_rpm", None) or current_app.config.get("DEFAULT_RATE_LIMIT_RPM", 60)

    now = int(time.time())
    window = 60
    bucket_key = _key(scope, api_key)
    reset = now - (now % window) + window

    if redis_client:
        pipe = redis_client.pipeline()
        pipe.incr(bucket_key, 1)
        pipe.expireat(bucket_key, reset)
        count, _ = pipe.execute()
        remaining = max(0, limit - int(count))
        return RateLimit(limit=limit, remaining=remaining, reset=reset)

    # Fallback in-memory counter (per-process)
    store = getattr(current_app, "_rl_store", None)
    if store is None:
        store = {}
        current_app._rl_store = store  # type: ignore
    # reset bucket if expired
    bucket = store.get(bucket_key)
    if not bucket or bucket[1] <= now:
        store[bucket_key] = [0, reset]
    store[bucket_key][0] += 1
    count, reset_ts = store[bucket_key]
    remaining = max(0, limit - int(count))
    return RateLimit(limit=limit, remaining=remaining, reset=reset_ts)

