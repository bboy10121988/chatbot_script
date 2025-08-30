import os
import sys
import bcrypt

from app import create_app
from app.extensions import db
from app.models import Tenant, ApiKey, Product, KeywordRule


def main():
    api_key_plain = os.getenv("SEED_API_KEY", "demo_key")
    tenant_name = os.getenv("SEED_TENANT_NAME", "demo")

    app = create_app()
    with app.app_context():
        # Create tables if they don't exist (works for MySQL as well)
        db.create_all()

        tenant = Tenant.query.filter_by(name=tenant_name).first()
        if not tenant:
            tenant = Tenant(name=tenant_name)
            db.session.add(tenant)
            db.session.flush()

        key = ApiKey.query.filter_by(tenant_id=tenant.id).first()
        if not key:
            key_hash = bcrypt.hashpw(api_key_plain.encode("utf-8"), bcrypt.gensalt())
            key = ApiKey(tenant_id=tenant.id, key_hash=key_hash, label='seed', rate_limit_rpm=60, is_active=True)
            db.session.add(key)

        # Ensure at least one product and rule
        p = Product.query.filter_by(tenant_id=tenant.id, name='真无线蓝牙耳机').first()
        if not p:
            p = Product(
                tenant_id=tenant.id,
                name='真无线蓝牙耳机',
                price=299.00,
                currency='CNY',
                image_url='https://via.placeholder.com/96',
                stock=100,
                is_active=True,
                tags=['蓝牙','耳机']
            )
            db.session.add(p)
            db.session.flush()

        r = KeywordRule.query.filter_by(tenant_id=tenant.id, trigger_text='蓝牙耳机').first()
        if not r:
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
        print(f"Seeded tenant='{tenant.name}' API_KEY='{api_key_plain}' (stored as bcrypt)")


if __name__ == "__main__":
    main()

