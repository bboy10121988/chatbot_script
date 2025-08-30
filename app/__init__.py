from flask import Flask, jsonify, request, g
from flask_cors import CORS

from .config import Config
from .extensions import db, migrate, init_redis
from .bootstrap import bootstrap_if_needed


def register_error_handlers(app: Flask):
    @app.errorhandler(400)
    def bad_request(e):
        return jsonify({"error": {"code": "bad_request", "message": str(e)}}), 400

    @app.errorhandler(401)
    def unauthorized(e):
        return jsonify({"error": {"code": "unauthorized", "message": "Unauthorized"}}), 401

    @app.errorhandler(403)
    def forbidden(e):
        return jsonify({"error": {"code": "forbidden", "message": "Forbidden"}}), 403

    @app.errorhandler(404)
    def not_found(e):
        return jsonify({"error": {"code": "not_found", "message": "Not found"}}), 404

    @app.errorhandler(429)
    def too_many(e):
        return jsonify({"error": {"code": "rate_limited", "message": "Too many requests"}}), 429

    @app.errorhandler(500)
    def server_error(e):
        return jsonify({"error": {"code": "server_error", "message": "Internal server error"}}), 500


def create_app(config_object: type[Config] | None = None):
    app = Flask(__name__, static_folder=None)
    app.config.from_object(config_object or Config)

    # CORS: Allow specific origins only (exact match); allow custom headers
    CORS(
        app,
        supports_credentials=False,
        origins=app.config.get("CORS_ALLOWED_ORIGINS") or [],
        allow_headers=["Content-Type", "X-API-Key"],
        expose_headers=["Content-Type"],
    )

    # Init extensions
    db.init_app(app)
    migrate.init_app(app, db)
    init_redis(app)

    # Dev helper: auto create tables for SQLite
    try:
        if app.config.get("AUTO_CREATE_DB") and str(app.config.get("SQLALCHEMY_DATABASE_URI", "")).startswith("sqlite"):
            with app.app_context():
                db.create_all()
    except Exception:
        pass

    # Blueprints
    from .routes.health import bp as health_bp
    from .routes.products import bp as products_bp
    from .routes.cart import bp as cart_bp
    from .routes.chat import bp as chat_bp
    from .routes.static import bp as static_bp
    from .routes.admin import bp as admin_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(products_bp, url_prefix="/v1")
    app.register_blueprint(cart_bp, url_prefix="/v1")
    app.register_blueprint(chat_bp, url_prefix="/v1")
    app.register_blueprint(admin_bp, url_prefix="/v1")
    app.register_blueprint(static_bp)

    register_error_handlers(app)

    # Finalize bootstrapping (first-run seeding when enabled)
    try:
        with app.app_context():
            bootstrap_if_needed()
    except Exception:
        pass
    return app
