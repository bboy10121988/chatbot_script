from __future__ import annotations

from decimal import Decimal
from flask import current_app

from .extensions import db
from .models import Tenant, ApiKey, Product, KeywordRule, Setting


def _bcrypt_hash(raw: str) -> bytes:
    import bcrypt
    return bcrypt.hashpw(raw.encode("utf-8"), bcrypt.gensalt())


def bootstrap_if_needed():
    app = current_app
    if not app.config.get("AUTO_BOOTSTRAP", False):
        return

    # Ensure tables exist
    try:
        db.create_all()
    except Exception:
        return

    # If at least one tenant exists, consider bootstrapped
    try:
        any_tenant = db.session.query(Tenant.id).limit(1).first()
    except Exception:
        return
    if any_tenant:
        return

    # Create demo tenant and API key
    tenant_name = app.config.get("SITE_TENANT_NAME", "demo")
    api_key_plain = app.config.get("SITE_API_KEY", "demo_key")

    tenant = Tenant(name=tenant_name)
    db.session.add(tenant)
    db.session.flush()

    key = ApiKey(tenant_id=tenant.id, key_hash=_bcrypt_hash(api_key_plain), label="site", rate_limit_rpm=60, is_active=True)
    db.session.add(key)

    # Default settings
    welcome_text = '嗨～我是商品助理。輸入關鍵字像是：藍牙耳機、耳機、充電器，我可以為你推薦商品。'
    default_reply_text = '暫時沒有找到相關商品，試試輸入：藍牙耳機、耳機、充電器。'
    db.session.add(Setting(tenant_id=tenant.id, key='welcome_text', value=welcome_text))
    db.session.add(Setting(tenant_id=tenant.id, key='default_reply_text', value=default_reply_text))

    if app.config.get("BOOTSTRAP_SAMPLE_DATA", True):
        p = Product(
            tenant_id=tenant.id,
            name='真无线蓝牙耳机',
            price=Decimal('299.00'),
            currency='CNY',
            image_url='https://via.placeholder.com/96',
            stock=100,
            is_active=True,
            tags=['蓝牙','耳机']
        )
        db.session.add(p)
        db.session.flush()

        r = KeywordRule(
            tenant_id=tenant.id,
            trigger_text='蓝牙耳机',
            match_type='contains',
            priority=100,
            product_ids=[p.id],
            response_text='为你推荐以下蓝牙耳机：',
            is_active=True,
        )
        db.session.add(r)

    db.session.commit()
    app.logger.info("Bootstrap completed: tenant='%s' api_key set via env SITE_API_KEY", tenant_name)

