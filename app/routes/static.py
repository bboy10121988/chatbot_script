from __future__ import annotations

import os
from flask import Blueprint, send_from_directory, current_app

bp = Blueprint("static_embed", __name__)


@bp.get("/embed.js")
def embed_js():
    # Serve from project-level public/, not app/public
    public_dir = os.path.abspath(os.path.join(current_app.root_path, os.pardir, "public"))
    return send_from_directory(public_dir, "embed.js", mimetype="application/javascript")


@bp.get("/admin")
def admin_page():
    # Serve admin UI (index.html) from repo root so that backend+frontend can be same-origin on Render
    root_dir = os.path.abspath(os.path.join(current_app.root_path, os.pardir))
    return send_from_directory(root_dir, "index.html", mimetype="text/html")
