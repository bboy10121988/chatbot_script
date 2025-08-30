from __future__ import annotations

from decimal import Decimal
from flask import Blueprint, jsonify, request, g

from ..auth import require_api_key
from ..extensions import db
from ..models import Cart, CartItem, Conversation, Product
from ..ratelimit import check_rate_limit

bp = Blueprint("cart", __name__)


@bp.before_request
def _auth():
    if request.method != 'OPTIONS':
        require_api_key()


@bp.post("/cart/items")
def add_item():
    rl = check_rate_limit(scope="cart", rpm=getattr(g, "rate_limit_rpm", None))
    if rl.remaining <= 0:
        return jsonify({"error": {"code": "rate_limited", "message": "Too many requests"}}), 429

    data = request.get_json(silent=True) or {}
    conversation_id = data.get("conversation_id")
    product_id = data.get("product_id")
    quantity = int(data.get("quantity") or 1)
    if not product_id or quantity <= 0:
        return jsonify({"error": {"code": "bad_request", "message": "Missing product_id or invalid quantity"}}), 400

    product = (
        db.session.query(Product)
        .filter(Product.id == int(product_id), Product.tenant_id == g.tenant_id, Product.is_active.is_(True))
        .first()
    )
    if not product:
        return jsonify({"error": {"code": "not_found", "message": "Product not found"}}), 404

    cart = (
        db.session.query(Cart)
        .filter(Cart.tenant_id == g.tenant_id, Cart.status == 'open', Cart.conversation_id == conversation_id)
        .first()
        if conversation_id
        else None
    )
    if not cart:
        cart = Cart(tenant_id=g.tenant_id, conversation_id=conversation_id, currency=product.currency)
        db.session.add(cart)
        db.session.flush()

    item = (
        db.session.query(CartItem)
        .filter(CartItem.cart_id == cart.id, CartItem.product_id == product.id)
        .first()
    )
    if item:
        item.quantity += quantity
    else:
        item = CartItem(
            cart_id=cart.id,
            product_id=product.id,
            quantity=quantity,
            unit_price=Decimal(product.price)
        )
        db.session.add(item)

    db.session.commit()

    # snapshot
    items = (
        db.session.query(CartItem)
        .filter(CartItem.cart_id == cart.id)
        .all()
    )
    total = sum([float(i.unit_price) * i.quantity for i in items])
    return jsonify({
        "cart_id": cart.id,
        "status": cart.status,
        "items": [
            {
                "product_id": i.product_id,
                "name": i.product.name,
                "quantity": i.quantity,
                "unit_price": float(i.unit_price),
                "currency": i.product.currency,
            } for i in items
        ],
        "total": {"value": total, "currency": cart.currency},
    })

