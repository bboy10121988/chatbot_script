from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import func
from .extensions import db


class Tenant(db.Model):
    __tablename__ = 'tenants'
    __table_args__ = {'sqlite_autoincrement': True}

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(120), nullable=False)
    status = db.Column(db.Enum('active', 'disabled', name='tenant_status'), nullable=False, default='active')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)


class ApiKey(db.Model):
    __tablename__ = 'api_keys'
    __table_args__ = {'sqlite_autoincrement': True}

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    key_hash = db.Column(db.LargeBinary(128), nullable=False)
    label = db.Column(db.String(120))
    rate_limit_rpm = db.Column(db.Integer, nullable=False, default=60)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    tenant = db.relationship('Tenant')


class Product(db.Model):
    __tablename__ = 'products'
    __table_args__ = {'sqlite_autoincrement': True}

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), index=True, nullable=False)
    sku = db.Column(db.String(64), unique=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    currency = db.Column(db.String(3), nullable=False, default='CNY')
    image_url = db.Column(db.String(512))
    stock = db.Column(db.Integer, nullable=False, default=0)
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    tags = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = db.relationship('Tenant')


class KeywordRule(db.Model):
    __tablename__ = 'keyword_rules'
    __table_args__ = {'sqlite_autoincrement': True}

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), index=True, nullable=False)
    trigger_text = db.Column(db.String(255), index=True, nullable=False)
    match_type = db.Column(db.Enum('exact', 'prefix', 'contains', 'regex', name='match_type'), nullable=False, default='contains')
    locale = db.Column(db.String(10))
    priority = db.Column(db.Integer, nullable=False, default=0)
    product_ids = db.Column(db.JSON)
    response_text = db.Column(db.String(500))
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = db.relationship('Tenant')


class Synonym(db.Model):
    __tablename__ = 'synonyms'
    __table_args__ = {'sqlite_autoincrement': True}

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), index=True, nullable=False)
    term = db.Column(db.String(255), index=True, nullable=False)
    synonyms = db.Column(db.JSON, nullable=False)
    locale = db.Column(db.String(10))
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    tenant = db.relationship('Tenant')


class Conversation(db.Model):
    __tablename__ = 'conversations'
    __table_args__ = {'sqlite_autoincrement': True}

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), index=True, nullable=False)
    external_user_id = db.Column(db.String(120))
    session_token = db.Column(db.String(120))
    status = db.Column(db.Enum('open', 'closed', name='conv_status'), nullable=False, default='open')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = db.relationship('Tenant')


class Message(db.Model):
    __tablename__ = 'messages'
    __table_args__ = {'sqlite_autoincrement': True}

    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), index=True, nullable=False)
    role = db.Column(db.Enum('user', 'assistant', 'system', name='msg_role'), nullable=False)
    content = db.Column(db.Text, nullable=False)
    content_type = db.Column(db.Enum('text', 'json', name='msg_type'), nullable=False, default='text')
    meta = db.Column('metadata', db.JSON)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    conversation = db.relationship('Conversation')


class Cart(db.Model):
    __tablename__ = 'carts'
    __table_args__ = {'sqlite_autoincrement': True}

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), index=True, nullable=False)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'))
    external_user_id = db.Column(db.String(120))
    status = db.Column(db.Enum('open', 'checked_out', 'abandoned', name='cart_status'), nullable=False, default='open')
    currency = db.Column(db.String(3), nullable=False, default='CNY')
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = db.relationship('Tenant')
    conversation = db.relationship('Conversation')


class CartItem(db.Model):
    __tablename__ = 'cart_items'
    __table_args__ = {'sqlite_autoincrement': True}

    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('carts.id'), index=True, nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)
    unit_price = db.Column(db.Numeric(10, 2), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    cart = db.relationship('Cart', backref=db.backref('items', lazy='dynamic'))
    product = db.relationship('Product')


class Setting(db.Model):
    __tablename__ = 'settings'
    __table_args__ = {'sqlite_autoincrement': True}

    id = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), index=True, nullable=False)
    key = db.Column(db.String(64), nullable=False)
    value = db.Column(db.JSON, nullable=True)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    tenant = db.relationship('Tenant')
