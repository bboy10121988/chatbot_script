from __future__ import annotations

from flask import Blueprint, jsonify, request, g

from ..auth import require_api_key
from ..extensions import db
from ..models import KeywordRule, Setting, Product
from ..cache import get as cache_get, set as cache_set, delete as cache_delete
from decimal import Decimal
import json
import typing as t
import requests

bp = Blueprint("admin", __name__)


@bp.before_request
def _auth():
    if request.method != 'OPTIONS':
        require_api_key()


# Keyword rules CRUD
@bp.get("/keyword-rules")
def list_rules():
    q = db.session.query(KeywordRule).filter(
        KeywordRule.tenant_id == g.tenant_id
    ).order_by(KeywordRule.priority.desc(), KeywordRule.id.desc())
    rules = [serialize_rule(r) for r in q.all()]
    return jsonify(rules)


@bp.post("/keyword-rules")
def create_rule():
    data = request.get_json(silent=True) or {}
    try:
        r = KeywordRule(
            tenant_id=g.tenant_id,
            trigger_text=(data.get("trigger_text") or "").strip(),
            match_type=(data.get("match_type") or "contains"),
            priority=int(data.get("priority") or 0),
            product_ids=data.get("product_ids") or [],
            response_text=data.get("response_text"),
            is_active=bool(data.get("is_active", True)),
        )
        if not r.trigger_text:
            return jsonify({"error": {"code": "bad_request", "message": "trigger_text required"}}), 400
        db.session.add(r)
        db.session.commit()
        return jsonify(serialize_rule(r)), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": {"code": "bad_request", "message": str(e)}}), 400


@bp.put("/keyword-rules/<int:rule_id>")
def update_rule(rule_id: int):
    r = db.session.get(KeywordRule, rule_id)
    if not r or r.tenant_id != g.tenant_id:
        return jsonify({"error": {"code": "not_found", "message": "rule not found"}}), 404
    data = request.get_json(silent=True) or {}
    for field in ["trigger_text", "match_type", "priority", "product_ids", "response_text", "is_active"]:
        if field in data:
            setattr(r, field, data[field])
    db.session.commit()
    return jsonify(serialize_rule(r))


@bp.delete("/keyword-rules/<int:rule_id>")
def delete_rule(rule_id: int):
    r = db.session.get(KeywordRule, rule_id)
    if not r or r.tenant_id != g.tenant_id:
        return jsonify({"error": {"code": "not_found", "message": "rule not found"}}), 404
    db.session.delete(r)
    db.session.commit()
    return jsonify({"ok": True})


def serialize_rule(r: KeywordRule):
    return {
        "id": r.id,
        "trigger_text": r.trigger_text,
        "match_type": r.match_type,
        "priority": r.priority,
        "product_ids": r.product_ids or [],
        "response_text": r.response_text,
        "is_active": bool(r.is_active),
    }


# Settings (welcome/default replies)
ALLOWED_SETTING_KEYS = {"welcome_text", "default_reply_text", "external_products_api_url", "external_products_api_key", "suggested_queries"}


@bp.get("/settings")
def get_settings():
    try:
        cache_key = f"{g.tenant_id}:settings"
        cached = cache_get("settings", cache_key)
        if cached is not None:
            return jsonify(cached)
        rows = (
            db.session.query(Setting)
            .filter(Setting.tenant_id == g.tenant_id, Setting.key.in_(ALLOWED_SETTING_KEYS))
            .all()
        )
        res = {s.key: s.value for s in rows}
        cache_set("settings", cache_key, res, ttl_seconds=60)
        return jsonify(res)
    except Exception:
        # If the table is missing (e.g., first boot), attempt to create it then return defaults
        try:
            db.create_all()
        except Exception:
            pass
        return jsonify({})


@bp.put("/settings")
def update_settings():
    data = request.get_json(silent=True) or {}
    updated = {}
    try:
        for k, v in data.items():
            if k not in ALLOWED_SETTING_KEYS:
                continue
            row = (
                db.session.query(Setting)
                .filter(Setting.tenant_id == g.tenant_id, Setting.key == k)
                .first()
            )
            if not row:
                row = Setting(tenant_id=g.tenant_id, key=k, value=v)
                db.session.add(row)
            else:
                row.value = v
            updated[k] = v
        db.session.commit()
    except Exception:
        # Attempt to create tables and retry once
        try:
            db.create_all()
            for k, v in data.items():
                if k not in ALLOWED_SETTING_KEYS:
                    continue
                row = (
                    db.session.query(Setting)
                    .filter(Setting.tenant_id == g.tenant_id, Setting.key == k)
                    .first()
                )
                if not row:
                    row = Setting(tenant_id=g.tenant_id, key=k, value=v)
                    db.session.add(row)
                else:
                    row.value = v
                updated[k] = v
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({"error": {"code": "server_error", "message": str(e)}}), 500
    # invalidate cache
    cache_delete("settings", f"{g.tenant_id}:settings")
    return jsonify(updated)


# Admin Products CRUD
@bp.get("/admin/products")
def admin_list_products():
    limit = min(int(request.args.get("limit", 100)), 500)
    offset = int(request.args.get("offset", 0))
    q = (
        db.session.query(Product)
        .filter(Product.tenant_id == g.tenant_id)
        .order_by(Product.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return jsonify([serialize_product(p) for p in q])


@bp.post("/admin/products")
def admin_create_product():
    data = request.get_json(silent=True) or {}
    try:
        p = Product(
            tenant_id=g.tenant_id,
            sku=data.get("sku"),
            name=(data.get("name") or "").strip(),
            description=data.get("description"),
            price=Decimal(str(data.get("price") or 0)),
            currency=(data.get("currency") or "CNY"),
            image_url=data.get("image_url"),
            stock=int(data.get("stock") or 0),
            is_active=bool(data.get("is_active", True)),
            tags=data.get("tags") or [],
        )
        if not p.name:
            return jsonify({"error": {"code": "bad_request", "message": "name required"}}), 400
        db.session.add(p)
        db.session.commit()
        return jsonify(serialize_product(p)), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": {"code": "bad_request", "message": str(e)}}), 400


@bp.put("/admin/products/<int:pid>")
def admin_update_product(pid: int):
    p = db.session.get(Product, pid)
    if not p or p.tenant_id != g.tenant_id:
        return jsonify({"error": {"code": "not_found", "message": "product not found"}}), 404
    data = request.get_json(silent=True) or {}
    for k in ["sku","name","description","currency","image_url"]:
        if k in data:
            setattr(p, k, data[k])
    if "price" in data:
        p.price = Decimal(str(data["price"]))
    if "stock" in data:
        p.stock = int(data["stock"])
    if "is_active" in data:
        p.is_active = bool(data["is_active"])
    if "tags" in data:
        p.tags = data["tags"]
    db.session.commit()
    return jsonify(serialize_product(p))


@bp.delete("/admin/products/<int:pid>")
def admin_delete_product(pid: int):
    p = db.session.get(Product, pid)
    if not p or p.tenant_id != g.tenant_id:
        return jsonify({"error": {"code": "not_found", "message": "product not found"}}), 404
    db.session.delete(p)
    db.session.commit()
    return jsonify({"ok": True})


def serialize_product(p: Product):
    return {
        "id": p.id,
        "sku": p.sku,
        "name": p.name,
        "description": p.description,
        "price": float(p.price),
        "currency": p.currency,
        "image_url": p.image_url,
        "stock": p.stock,
        "is_active": bool(p.is_active),
        "tags": p.tags or [],
    }


@bp.post("/admin/products/import")
def admin_import_products():
    # Read settings
    url_row = db.session.query(Setting).filter(Setting.tenant_id==g.tenant_id, Setting.key=='external_products_api_url').first()
    key_row = db.session.query(Setting).filter(Setting.tenant_id==g.tenant_id, Setting.key=='external_products_api_key').first()
    api_url = (url_row.value if url_row else None) or (request.json or {}).get('api_url')
    api_key = (key_row.value if key_row else None) or (request.json or {}).get('api_key')
    if not api_url:
        return jsonify({"error": {"code": "bad_request", "message": "external_products_api_url not configured"}}), 400

    headers = {"Accept": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    try:
        resp = requests.get(api_url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if not isinstance(data, list):
            return jsonify({"error": {"code": "bad_response", "message": "expected JSON array"}}), 502
    except Exception as e:
        return jsonify({"error": {"code": "upstream_error", "message": str(e)}}), 502

    created = 0
    updated = 0
    for item in data:
        if not isinstance(item, dict):
            continue
        sku = item.get('sku')
        name = (item.get('name') or '').strip()
        if not name and not sku:
            continue
        q = db.session.query(Product).filter(Product.tenant_id==g.tenant_id)
        if sku:
            q = q.filter(Product.sku==sku)
        else:
            q = q.filter(Product.name==name)
        p = q.first()
        if not p:
            p = Product(tenant_id=g.tenant_id)
            created += 1
        else:
            updated += 1
        p.sku = sku
        p.name = name or p.name
        p.description = item.get('description')
        try:
            p.price = Decimal(str(item.get('price') or 0))
        except Exception:
            p.price = Decimal('0')
        p.currency = item.get('currency') or 'CNY'
        p.image_url = item.get('image_url')
        try:
            p.stock = int(item.get('stock') or 0)
        except Exception:
            p.stock = 0
        p.is_active = bool(item.get('is_active', True))
        tags = item.get('tags')
        if isinstance(tags, str):
            # allow comma-separated
            tags = [t.strip() for t in tags.split(',') if t.strip()]
        p.tags = tags if isinstance(tags, list) else []
        db.session.add(p)
    db.session.commit()
    return jsonify({"ok": True, "created": created, "updated": updated})


@bp.get("/admin/products/export")
def admin_export_products():
    from io import StringIO
    import csv
    items = (
        db.session.query(Product)
        .filter(Product.tenant_id == g.tenant_id)
        .order_by(Product.id.asc())
        .all()
    )
    out = StringIO()
    writer = csv.writer(out)
    writer.writerow(["id","sku","name","description","price","currency","image_url","stock","is_active","tags"])
    for p in items:
        writer.writerow([p.id, p.sku or '', p.name, p.description or '', float(p.price), p.currency, p.image_url or '', p.stock, 1 if p.is_active else 0, ','.join(p.tags or [])])
    return (out.getvalue(), 200, {"Content-Type": "text/csv; charset=utf-8", "Content-Disposition": "attachment; filename=products.csv"})


@bp.post("/admin/products/import-csv")
def admin_import_products_csv():
    from io import StringIO
    import csv
    raw = request.get_data(as_text=True)
    if not raw:
        return jsonify({"error": {"code": "bad_request", "message": "empty body"}}), 400
    reader = csv.DictReader(StringIO(raw))
    created = updated = 0
    for row in reader:
        sku = (row.get('sku') or '').strip() or None
        name = (row.get('name') or '').strip()
        if not (sku or name):
            continue
        q = db.session.query(Product).filter(Product.tenant_id == g.tenant_id)
        if sku: q = q.filter(Product.sku == sku)
        else: q = q.filter(Product.name == name)
        p = q.first()
        if not p:
            p = Product(tenant_id=g.tenant_id)
            created += 1
        else:
            updated += 1
        p.sku = sku
        p.name = name or p.name
        p.description = row.get('description')
        try: p.price = Decimal(str(row.get('price') or 0))
        except Exception: p.price = Decimal('0')
        p.currency = row.get('currency') or 'CNY'
        p.image_url = row.get('image_url')
        try: p.stock = int(row.get('stock') or 0)
        except Exception: p.stock = 0
        p.is_active = str(row.get('is_active') or '1') in ('1','true','True')
        tags_raw = row.get('tags')
        if tags_raw: p.tags = [t.strip() for t in tags_raw.split(',') if t.strip()]
        db.session.add(p)
    db.session.commit()
    return jsonify({"ok": True, "created": created, "updated": updated})


@bp.get("/keyword-rules/export")
def export_rules():
    from io import StringIO
    import csv
    items = (
        db.session.query(KeywordRule)
        .filter(KeywordRule.tenant_id == g.tenant_id)
        .order_by(KeywordRule.priority.desc(), KeywordRule.id.asc())
        .all()
    )
    out = StringIO()
    writer = csv.writer(out)
    writer.writerow(["id","trigger_text","match_type","priority","product_ids","response_text","is_active"]) 
    for r in items:
        writer.writerow([r.id, r.trigger_text, r.match_type, r.priority, ','.join([str(x) for x in (r.product_ids or [])]), r.response_text or '', 1 if r.is_active else 0])
    return (out.getvalue(), 200, {"Content-Type": "text/csv; charset=utf-8", "Content-Disposition": "attachment; filename=keyword_rules.csv"})


@bp.post("/keyword-rules/import-csv")
def import_rules_csv():
    from io import StringIO
    import csv
    raw = request.get_data(as_text=True)
    if not raw:
        return jsonify({"error": {"code": "bad_request", "message": "empty body"}}), 400
    reader = csv.DictReader(StringIO(raw))
    created = updated = 0
    for row in reader:
        trig = (row.get('trigger_text') or '').strip()
        if not trig:
            continue
        r = db.session.query(KeywordRule).filter(KeywordRule.tenant_id == g.tenant_id, KeywordRule.trigger_text == trig).first()
        if not r:
            r = KeywordRule(tenant_id=g.tenant_id)
            created += 1
        else:
            updated += 1
        r.trigger_text = trig
        r.match_type = (row.get('match_type') or 'contains')
        try: r.priority = int(row.get('priority') or 0)
        except Exception: r.priority = 0
        pids = (row.get('product_ids') or '').strip()
        r.product_ids = [int(x) for x in pids.split(',') if x.strip().isdigit()] if pids else []
        r.response_text = row.get('response_text') or None
        r.is_active = str(row.get('is_active') or '1') in ('1','true','True')
        db.session.add(r)
    db.session.commit()
    # invalidate settings cache is unnecessary here
    return jsonify({"ok": True, "created": created, "updated": updated})
