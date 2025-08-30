from __future__ import annotations

import base64
from typing import Optional

from flask import request, g, current_app, abort

from .extensions import db
from .models import ApiKey


def verify_bcrypt_hash(hashed: bytes, raw: str) -> bool:
    try:
        import bcrypt

        return bcrypt.checkpw(raw.encode("utf-8"), hashed)
    except Exception:
        return False


def find_api_key(raw_key: str) -> Optional[ApiKey]:
    # Naive scan of active keys. For scale, store key_id prefix and index.
    q = db.session.query(ApiKey).filter(ApiKey.is_active.is_(True))
    for key in q:  # type: ignore
        if verify_bcrypt_hash(key.key_hash, raw_key):
            return key
    return None


def cors_origin_allowed(origin: str | None) -> bool:
    if not origin:
        return False
    allowed = current_app.config.get("CORS_ALLOWED_ORIGINS") or []
    return origin in allowed


def require_api_key():
    hdr = request.headers.get("X-API-Key")
    origin = request.headers.get("Origin")

    # In development, relax Origin check to reduce friction
    if not cors_origin_allowed(origin):
        if not current_app.debug:
            abort(403)

    if not hdr:
        abort(401)

    key = find_api_key(hdr)
    if not key:
        abort(401)

    g.api_key = hdr
    g.api_key_row = key
    g.tenant_id = key.tenant_id
    g.rate_limit_rpm = key.rate_limit_rpm
