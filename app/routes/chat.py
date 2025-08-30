from __future__ import annotations

from flask import Blueprint, jsonify, request, g

from ..auth import require_api_key
from ..extensions import db
from ..models import Conversation, Message
from ..ratelimit import check_rate_limit
from ..services.recommendation import recommend
from ..models import Setting, Conversation

bp = Blueprint("chat", __name__)


@bp.before_request
def _auth():
    if request.method != 'OPTIONS':
        require_api_key()


@bp.post("/chat/message")
def chat_message():
    rl = check_rate_limit(scope="chat", rpm=getattr(g, "rate_limit_rpm", None))
    if rl.remaining <= 0:
        return jsonify({"error": {"code": "rate_limited", "message": "Too many requests"}}), 429

    data = request.get_json(silent=True) or {}
    message = (data.get("message") or "").strip()
    if not message:
        return jsonify({"error": {"code": "bad_request", "message": "Message required"}}), 400

    conversation_id = data.get("conversation_id")
    convo = None
    if conversation_id:
        convo = db.session.query(Conversation).filter(Conversation.id == int(conversation_id), Conversation.tenant_id == g.tenant_id).first()
    if not convo:
        convo = Conversation(tenant_id=g.tenant_id)
        db.session.add(convo)
        db.session.flush()

    # store user message
    um = Message(conversation_id=convo.id, role='user', content=message)
    db.session.add(um)

    resp_text, products = recommend(g.tenant_id, message, limit=5)

    messages = []
    # ensure there is at least one assistant text reply
    if not resp_text:
        # If有商品但無規則文案，用固定提示；若無商品，使用可配置的預設回覆
        if products:
            resp_text = "为你找到以下商品："
        else:
            default_row = (
                db.session.query(Setting).filter(Setting.tenant_id == g.tenant_id, Setting.key == 'default_reply_text').first()
            )
            default_reply = default_row.value if default_row and isinstance(default_row.value, str) else None
            resp_text = default_reply or "暫時沒有找到相關商品，試試輸入：藍牙耳機、耳機、充電器。"
    if resp_text:
        am = Message(conversation_id=convo.id, role='assistant', content=resp_text)
        db.session.add(am)
        messages.append({"role": "assistant", "type": "text", "content": resp_text})

    db.session.commit()

    product_cards = [
        {
            "id": p.id,
            "name": p.name,
            "image_url": p.image_url,
            "price": {"value": float(p.price), "currency": p.currency},
            "tags": p.tags or [],
            "add_to_cart": {"product_id": p.id, "default_qty": 1},
        }
        for p in products
    ]

    return jsonify({
        "conversation_id": convo.id,
        "messages": messages,
        "products": product_cards,
    })


@bp.post("/chat/reset")
def chat_reset():
    """Close an existing conversation (if any).
    Client should clear its local conversation state after this call.
    """
    data = request.get_json(silent=True) or {}
    conversation_id = data.get("conversation_id")
    if conversation_id:
        try:
            cid = int(conversation_id)
        except Exception:
            return jsonify({"error": {"code": "bad_request", "message": "invalid conversation_id"}}), 400
        convo = db.session.query(Conversation).filter(Conversation.id == cid, Conversation.tenant_id == g.tenant_id).first()
        if convo:
            convo.status = 'closed'
            db.session.commit()
    return jsonify({"ok": True})
