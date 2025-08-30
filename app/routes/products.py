from __future__ import annotations

from flask import Blueprint, jsonify, request, g

from ..auth import require_api_key
from ..extensions import db
from ..models import Product

bp = Blueprint("products", __name__)


@bp.before_request
def _auth():
    if request.method != 'OPTIONS':
        require_api_key()


@bp.get("/products/<int:product_id>")
def get_product(product_id: int):
    p = (
        db.session.query(Product)
        .filter(Product.id == product_id, Product.tenant_id == g.tenant_id, Product.is_active.is_(True))
        .first()
    )
    if not p:
        return jsonify({"error": {"code": "not_found", "message": "Product not found"}}), 404
    return jsonify(_product_payload(p))


@bp.get("/products")
def list_products():
    ids = request.args.get("ids")
    if not ids:
        return jsonify([])
    try:
        id_list = [int(x) for x in ids.split(",")]
    except Exception:
        return jsonify({"error": {"code": "bad_request", "message": "Invalid ids"}}), 400
    qs = (
        db.session.query(Product)
        .filter(Product.tenant_id == g.tenant_id, Product.is_active.is_(True), Product.id.in_(id_list))
        .all()
    )
    return jsonify([_product_payload(p) for p in qs])


def _product_payload(p: Product):
    return {
        "id": p.id,
        "name": p.name,
        "image_url": p.image_url,
        "price": {"value": float(p.price), "currency": p.currency},
        "tags": p.tags or [],
    }

