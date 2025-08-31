from __future__ import annotations

import json
import time
from typing import Any, Optional

from .extensions import redis_client


_store: dict[str, tuple[float, Any]] = {}


def _now() -> float:
    return time.time()


def _key(namespace: str, key: str) -> str:
    return f"cb:{namespace}:{key}"


def get(namespace: str, key: str) -> Optional[Any]:
    k = _key(namespace, key)
    if redis_client:
        try:
            raw = redis_client.get(k)
            if raw is None:
                return None
            return json.loads(raw)
        except Exception:
            pass
    # in-memory
    item = _store.get(k)
    if not item:
        return None
    exp_ts, value = item
    if exp_ts < _now():
        _store.pop(k, None)
        return None
    return value


def set(namespace: str, key: str, value: Any, ttl_seconds: int = 60) -> None:
    k = _key(namespace, key)
    if redis_client:
        try:
            redis_client.setex(k, ttl_seconds, json.dumps(value, ensure_ascii=False))
            return
        except Exception:
            pass
    _store[k] = (_now() + ttl_seconds, value)


def delete(namespace: str, key: str) -> None:
    k = _key(namespace, key)
    if redis_client:
        try:
            redis_client.delete(k)
        except Exception:
            pass
    _store.pop(k, None)

