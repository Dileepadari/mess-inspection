"""MessCheck - Flask application factory."""

import os
from datetime import date, datetime
from pathlib import Path

from flask import Flask, render_template

from . import db
from .constants import APP_NAME, ORG_NAME

BASE_DIR = Path(__file__).resolve().parent.parent

__all__ = ["create_app"]


def create_app(test_config=None):
    app = Flask(__name__, instance_relative_config=True)
    app.config.from_mapping(
        SECRET_KEY=os.environ.get("MESSCHECK_SECRET_KEY", "dev-only-change-me"),
        DATABASE=os.environ.get("MESSCHECK_DB", str(BASE_DIR / "checklist.db")),
    )
    if test_config:
        app.config.update(test_config)

    db.init_app(app)

    from .views import fields as fields_view
    from .views import pages as pages_view
    from .views import records as records_view

    app.register_blueprint(pages_view.bp)
    app.register_blueprint(records_view.bp)
    app.register_blueprint(fields_view.bp)

    _register_template_helpers(app)
    _register_error_handlers(app)

    with app.app_context():
        db.init_db()

    return app


def _register_template_helpers(app):
    @app.context_processor
    def inject_globals():
        return {
            "app_name": APP_NAME,
            "org_name": ORG_NAME,
            "current_year": date.today().year,
        }

    @app.template_filter("pretty_date")
    def pretty_date(value):
        """Render an ISO date as e.g. 27 Aug 2026, leaving junk untouched."""
        try:
            return datetime.strptime(str(value), "%Y-%m-%d").strftime("%d %b %Y")
        except (ValueError, TypeError):
            return value or "-"

    @app.template_filter("pretty_time")
    def pretty_time(value):
        for fmt in ("%H:%M:%S", "%H:%M"):
            try:
                return datetime.strptime(str(value), fmt).strftime("%I:%M %p").lstrip("0")
            except (ValueError, TypeError):
                continue
        return value or "-"


def _register_error_handlers(app):
    @app.errorhandler(404)
    def not_found(error):
        return render_template("error.html", code=404,
                               message="We could not find that page."), 404

    @app.errorhandler(500)
    def server_error(error):  # pragma: no cover - exercised only on a real crash
        return render_template("error.html", code=500,
                               message="Something went wrong on our side."), 500
