import os
import sqlite3
import hmac
from pathlib import Path
from types import SimpleNamespace

from dotenv import load_dotenv
from flask import Flask, abort, g, current_app, request, session


PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def create_app(test_config=None):
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder=str(PROJECT_ROOT / "static"),
    )
    app.config.from_object("gaming_hub.config")
    if test_config:
        app.config.update(test_config)

    from .routes import main

    app.register_blueprint(main)
    app.teardown_appcontext(close_db)

    @app.before_request
    def protect_post_requests():
        if request.method == "POST":
            submitted_token = request.form.get("csrf_token", "")
            expected_token = session.get("csrf_token", "")
            if not expected_token or not hmac.compare_digest(
                submitted_token, expected_token
            ):
                abort(400, description="Invalid or missing CSRF token.")

    @app.context_processor
    def template_context():
        user_id = session.get("user_id")
        user = None
        if user_id is not None:
            row = get_db().execute(
                """
                SELECT id, username, email, first_name, last_name, is_staff,
                       is_superuser, is_active
                FROM auth_user WHERE id = ?
                """,
                (user_id,),
            ).fetchone()
            if row is not None and row["is_active"]:
                user = SimpleNamespace(**dict(row), is_authenticated=True)
            else:
                session.pop("user_id", None)
        if user is None:
            user = SimpleNamespace(is_authenticated=False, username="")
        return {"user": user, "csrf_token": csrf_token}

    @app.errorhandler(400)
    def bad_request(error):
        return f"Bad request: {error.description}", 400

    from .feature_auth import auth_rooms
    from .feature_stats import stats
    from .feature_competitions import competitions
    from .feature_admin import admin as admin_blueprint
    from .live_games import initialize_live_games, live_games

    app.register_blueprint(auth_rooms)
    app.register_blueprint(stats)
    app.register_blueprint(competitions)
    app.register_blueprint(admin_blueprint)
    app.register_blueprint(live_games)
    initialize_live_games(app.config["GAME_DATABASE"])
    return app


def csrf_token():
    token = session.get("csrf_token")
    if token is None:
        import secrets

        token = secrets.token_urlsafe(32)
        session["csrf_token"] = token
    return token


def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(current_app.config["DATABASE"], timeout=10)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exception=None):
    database = g.pop("db", None)
    if database is not None:
        database.close()
