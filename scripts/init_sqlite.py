from app import create_app
from app.extensions import db
from app.models import Tenant, ApiKey, Product, KeywordRule, Synonym, Setting
import bcrypt


def main():
    app = create_app()
    with app.app_context():
        db.create_all()

        tenant = Tenant.query.first()
        if not tenant:
            tenant = Tenant(name='demo')
            db.session.add(tenant)
            db.session.flush()

        # API key: demo_key
        api_key = ApiKey.query.filter_by(tenant_id=tenant.id).first()
        if not api_key:
            key_hash = bcrypt.hashpw(b"demo_key", bcrypt.gensalt())
            api_key = ApiKey(tenant_id=tenant.id, key_hash=key_hash, label='demo', rate_limit_rpm=60, is_active=True)
            db.session.add(api_key)

        # Products
        p1 = Product.query.filter_by(tenant_id=tenant.id, name='真无线蓝牙耳机').first()
        if not p1:
            p1 = Product(
                tenant_id=tenant.id,
                name='真无线蓝牙耳机',
                price=299.00,
                currency='CNY',
                image_url='https://via.placeholder.com/96',
                stock=100,
                is_active=True,
                tags=['蓝牙','耳机']
            )
            db.session.add(p1)
            db.session.flush()

        p2 = Product.query.filter_by(tenant_id=tenant.id, name='有线入耳式耳机').first()
        if not p2:
            p2 = Product(
                tenant_id=tenant.id,
                name='有线入耳式耳机',
                price=59.00,
                currency='CNY',
                image_url='https://via.placeholder.com/96',
                stock=200,
                is_active=True,
                tags=['有线','耳机']
            )
            db.session.add(p2)
            db.session.flush()

        p3 = Product.query.filter_by(tenant_id=tenant.id, name='快充充電器 20W').first()
        if not p3:
            p3 = Product(
                tenant_id=tenant.id,
                name='快充充電器 20W',
                price=129.00,
                currency='CNY',
                image_url='https://via.placeholder.com/96',
                stock=150,
                is_active=True,
                tags=['充電器','Type-C']
            )
            db.session.add(p3)
            db.session.flush()

        # Rules (多語/多關鍵字)
        rules = [
            dict(trigger_text='蓝牙耳机', priority=100, product_ids=[p1.id], response_text='为你推荐以下蓝牙耳机：'),
            dict(trigger_text='藍牙耳機', priority=100, product_ids=[p1.id], response_text='為你推薦以下藍牙耳機：'),
            dict(trigger_text='耳机', priority=50, product_ids=[p1.id, p2.id], response_text='以下耳机可供選擇：'),
            dict(trigger_text='耳機', priority=50, product_ids=[p1.id, p2.id], response_text='以下耳機可供選擇：'),
            dict(trigger_text='充電器', priority=80, product_ids=[p3.id], response_text='這些充電器可能適合你：'),
            dict(trigger_text='充电器', priority=80, product_ids=[p3.id], response_text='这些充电器可能适合你：'),
        ]
        for r in rules:
            exists = KeywordRule.query.filter_by(tenant_id=tenant.id, trigger_text=r['trigger_text']).first()
            if not exists:
                db.session.add(KeywordRule(
                    tenant_id=tenant.id,
                    trigger_text=r['trigger_text'],
                    match_type='contains',
                    priority=r['priority'],
                    product_ids=r['product_ids'],
                    response_text=r['response_text'],
                    is_active=True
                ))

        # Synonyms
        syn_map = [
            ('藍牙耳機', ['蓝牙耳机']),
            ('充電器', ['充电器']),
            ('耳機', ['耳机']),
        ]
        for term, syns in syn_map:
            if not Synonym.query.filter_by(tenant_id=tenant.id, term=term).first():
                db.session.add(Synonym(tenant_id=tenant.id, term=term, synonyms=syns))

        db.session.commit()
        # Seed settings
        def set_if_absent(k, v):
            if not Setting.query.filter_by(tenant_id=tenant.id, key=k).first():
                db.session.add(Setting(tenant_id=tenant.id, key=k, value=v))
        set_if_absent('welcome_text', '嗨～我是商品助理。輸入關鍵字像是：藍牙耳機、耳機、充電器，我可以為你推薦商品。')
        set_if_absent('default_reply_text', '暫時沒有找到相關商品，試試輸入：藍牙耳機、耳機、充電器。')
        db.session.commit()
        print("SQLite DB initialized. Demo API key: demo_key")


if __name__ == "__main__":
    main()
