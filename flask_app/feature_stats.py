from datetime import datetime, timezone
import os
from pathlib import Path
import re
from uuid import uuid4

from flask import Blueprint, abort, current_app, redirect, render_template, request, session, url_for
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

from . import PROJECT_ROOT, get_db
from .email import EmailConfigurationError, send_email


stats = Blueprint("stats", __name__)

GAMES = {
    "fifa": {
        "key": "fifa_mobile",
        "name": "FIFA Mobile",
        "icon": "⚽",
        "fields": (("goals", "Goals"), ("assists", "Assists"), ("wins", "Wins"), ("matches_played", "Matches played")),
        "columns": (("goals", "Goals"), ("assists", "Assists"), ("wins", "Wins"), ("matches_played", "Matches")),
    },
    "pubg": {
        "key": "pubg_mobile",
        "name": "PUBG Mobile",
        "icon": "🔫",
        "fields": (("kills", "Kills"), ("deaths", "Deaths"), ("wins", "Wins"), ("matches_played", "Matches played")),
        "columns": (("kills", "Kills"), ("deaths", "Deaths"), ("wins", "Wins"), ("matches_played", "Matches")),
    },
    "clash-of-clans": {
        "key": "clash_of_clans",
        "name": "Clash of Clans",
        "icon": "🏰",
        "fields": (("trophies", "Trophies"), ("town_hall_level", "Town Hall level"), ("wins", "Wins"), ("matches_played", "Matches played")),
        "columns": (("trophies", "Trophies"), ("town_hall_level", "Town Hall"), ("wins", "Wins"), ("matches_played", "Matches")),
    },
    "asphalt-9": {
        "key": "asphalt_9",
        "name": "Asphalt 9",
        "icon": "🏎️",
        "fields": (("wins", "Races won"), ("matches_played", "Races played")),
        "columns": (("wins", "Races won"), ("matches_played", "Races")),
    },
    "mobile-legends": {
        "key": "mobile_legends",
        "name": "Mobile Legends",
        "icon": "⚔️",
        "fields": (("kills", "Kills"), ("deaths", "Deaths"), ("assists", "Assists"), ("wins", "Wins"), ("matches_played", "Matches played")),
        "columns": (("kills", "Kills"), ("deaths", "Deaths"), ("assists", "Assists"), ("wins", "Wins"), ("matches_played", "Matches")),
    },
    "dream-league": {
        "key": "dream_league_soccer",
        "name": "Dream League Soccer",
        "icon": "🥅",
        "fields": (("goals", "Goals"), ("assists", "Assists"), ("wins", "Wins"), ("matches_played", "Matches played")),
        "columns": (("goals", "Goals"), ("assists", "Assists"), ("wins", "Wins"), ("matches_played", "Matches")),
    },
    "efootball": {
        "key": "efootball",
        "name": "eFootball",
        "icon": "🎮",
        "fields": (("goals", "Goals"), ("wins", "Wins"), ("matches_played", "Matches played")),
        "columns": (("goals", "Goals"), ("wins", "Wins"), ("matches_played", "Matches")),
    },
    "call-of-duty": {
        "key": "call_of_duty",
        "name": "Call of Duty",
        "icon": "🎯",
        "fields": (("kills", "Kills"), ("wins", "Wins"), ("matches_played", "Matches played")),
        "columns": (("kills", "Kills"), ("wins", "Wins"), ("matches_played", "Matches")),
    },
}

MAX_STAT_VALUE = 2_147_483_647
MAX_PROOF_SIZE = 10 * 1024 * 1024
PROOF_FORMATS = {
    ".jpg": ("JPEG", ".jpg"),
    ".jpeg": ("JPEG", ".jpg"),
    ".png": ("PNG", ".png"),
    ".gif": ("GIF", ".gif"),
    ".webp": ("WEBP", ".webp"),
}


def _current_user():
    """Resolve the session identity against existing user records."""
    user_id = session.get("user_id")
    if user_id is None:
        return None
    return get_db().execute(
        "SELECT id, username FROM auth_user WHERE id = ? AND is_active = 1",
        (user_id,),
    ).fetchone()


def _auth_required():
    user = _current_user()
    if user is None:
        return (
            None,
            redirect(url_for("auth_rooms.login", next=request.path)),
            302,
        )
    return user, None, None


def _score(game_key, values):
    if game_key == "fifa_mobile":
        return values.get("goals", 0) * 10 + values.get("wins", 0) * 100
    if game_key == "pubg_mobile":
        kills, deaths = values.get("kills", 0), values.get("deaths", 0)
        kd_bonus = kills * 50 // deaths if deaths else kills * 50
        return kills * 10 + values.get("wins", 0) * 150 + kd_bonus
    if game_key == "clash_of_clans":
        return values.get("trophies", 0) * 2 + values.get("town_hall_level", 1) * 1000
    return values.get("wins", 0) * 100


def _save_proof(upload):
    if upload is None or not upload.filename:
        return None, None

    safe_name = secure_filename(upload.filename)
    suffix = Path(safe_name).suffix.lower()
    expected = PROOF_FORMATS.get(suffix)
    if not safe_name or expected is None:
        return None, "Choose a PNG, JPEG, GIF, or WebP image file."

    upload.stream.seek(0, 2)
    file_size = upload.stream.tell()
    upload.stream.seek(0)
    if file_size > MAX_PROOF_SIZE:
        return None, "Proof images must be 10 MB or smaller."
    if file_size == 0:
        return None, "The selected proof image is empty."

    try:
        image = Image.open(upload.stream)
        if image.format != expected[0] or image.width * image.height > 40_000_000:
            return None, "The proof file must be a valid image matching its file extension."
        image.verify()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
    ):
        return None, "The proof file must be a valid PNG, JPEG, GIF, or WebP image."
    finally:
        upload.stream.seek(0)

    relative_path = Path("stat_screenshots") / datetime.now(timezone.utc).strftime("%Y/%m/%d")
    stored_name = f"{uuid4().hex}{expected[1]}"
    media_root = Path(current_app.config.get("MEDIA_ROOT", PROJECT_ROOT / "media"))
    destination = media_root / relative_path / stored_name
    destination.parent.mkdir(parents=True, exist_ok=True)
    upload.save(destination)
    return (relative_path / stored_name).as_posix(), None


@stats.route("/submit/<game_slug>/", methods=["GET", "POST"])
def submit_stats(game_slug):
    game = GAMES.get(game_slug)
    if game is None:
        abort(404)

    user, response, status = _auth_required()
    if response is not None:
        return response, status

    errors = []
    values = {}
    if request.method == "POST":
        for field, label in game["fields"]:
            raw_value = request.form.get(field, "").strip()
            try:
                value = int(raw_value)
                minimum = 1 if field in {"matches_played", "town_hall_level"} else 0
                if value < minimum or value > MAX_STAT_VALUE:
                    raise ValueError
                values[field] = value
            except (TypeError, ValueError):
                minimum = 1 if field in {"matches_played", "town_hall_level"} else 0
                errors.append(f"{label} must be a whole number between {minimum} and {MAX_STAT_VALUE}.")
        if "wins" in values and "matches_played" in values and values["wins"] > values["matches_played"]:
            errors.append("Wins cannot exceed matches played.")

        screenshot_path = None
        if not errors:
            screenshot_path, proof_error = _save_proof(request.files.get("screenshot"))
            if proof_error:
                errors.append(proof_error)

        if not errors:
            now = datetime.now(timezone.utc).isoformat(timespec="seconds")
            columns = ["user_id", "game_type", "wins", "matches_played"]
            params = [
                user["id"],
                game["key"],
                values.get("wins", 0),
                values.get("matches_played", 0),
            ]
            for field in ("goals", "kills", "assists", "deaths", "trophies", "town_hall_level"):
                columns.append(field)
                params.append(values.get(field, 1 if field == "town_hall_level" else 0))
            columns.extend(("screenshot", "description", "total_score", "created_at", "updated_at", "status", "verified"))
            params.extend((
                screenshot_path,
                request.form.get("description", "").strip()[:5000],
                _score(game["key"], values),
                now,
                now,
                "pending",
                0,
            ))
            placeholders = ", ".join("?" for _ in columns)
            try:
                database = get_db()
                database.execute(
                    f"INSERT INTO core_statsubmission ({', '.join(columns)}) VALUES ({placeholders})",
                    tuple(params),
                )
                database.commit()
            except Exception:
                if screenshot_path:
                    (
                        Path(current_app.config.get("MEDIA_ROOT", PROJECT_ROOT / "media"))
                        / screenshot_path
                    ).unlink(missing_ok=True)
                raise
            return redirect(url_for("stats.my_submissions", submitted=1))

    return render_template(
        "stats/submit.html",
        game=game,
        values=values,
        errors=errors,
        description=request.form.get("description", ""),
    )


@stats.get("/leaderboards/<game_slug>/")
def leaderboard(game_slug):
    game = GAMES.get(game_slug)
    if game is None:
        abort(404)
    entries = get_db().execute(
        """
        SELECT submission.id, submission.user_id, user.username, submission.wins,
               submission.matches_played, submission.goals, submission.kills,
               submission.assists, submission.deaths, submission.trophies,
               submission.town_hall_level, submission.total_score, submission.created_at
        FROM core_statsubmission AS submission
        JOIN auth_user AS user ON user.id = submission.user_id
        WHERE submission.game_type = ? AND submission.status = 'verified'
              AND submission.verified = 1
        ORDER BY submission.total_score DESC, submission.created_at ASC, submission.id ASC
        LIMIT 100
        """,
        (game["key"],),
    ).fetchall()
    return render_template(
        "stats/leaderboard.html",
        game=game,
        entries=entries,
        columns=game["columns"],
        total_players=len(entries),
        current_user_id=session.get("user_id"),
    )


@stats.get("/my-submissions/")
def my_submissions():
    user, response, status = _auth_required()
    if response is not None:
        return response, status
    database = get_db()
    submissions = database.execute(
        """
        SELECT id, game_type, wins, matches_played, goals, kills, assists,
               deaths, trophies, town_hall_level, screenshot, total_score, status,
               verified, verified_at, rejection_reason, created_at
        FROM core_statsubmission
        WHERE user_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (user["id"],),
    ).fetchall()
    counts = database.execute(
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN status = 'verified' THEN 1 ELSE 0 END) AS verified,
               SUM(CASE WHEN status = 'pending' THEN 1 ELSE 0 END) AS pending,
               SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) AS rejected
        FROM core_statsubmission
        WHERE user_id = ?
        """,
        (user["id"],),
    ).fetchone()
    game_names = {game["key"]: game["name"] for game in GAMES.values()}
    return render_template(
        "stats/my_submissions.html",
        submissions=submissions,
        counts={key: counts[key] or 0 for key in ("total", "verified", "pending", "rejected")},
        game_names=game_names,
        notice="Your submission was received for review." if request.args.get("submitted") == "1" else None,
    )


@stats.get("/select-game/")
def select_game():
    return render_template("stats/select_game.html", games=GAMES)


@stats.route("/contact/", methods=["GET", "POST"])
def contact():
    errors = []
    values = {
        "name": request.form.get("name", "").strip(),
        "email": request.form.get("email", "").strip(),
        "subject": request.form.get("subject", "").strip(),
        "message": request.form.get("message", "").strip(),
    }
    sent_attempt = False
    delivery_error = None
    delivered = False
    if request.method == "POST":
        if not values["name"] or len(values["name"]) > 100:
            errors.append("Enter your name (up to 100 characters).")
        if len(values["email"]) > 254 or not re.fullmatch(
            r"[^@\s]+@[^@\s]+\.[^@\s]+", values["email"]
        ):
            errors.append("Enter a valid email address.")
        if values["subject"] not in {"support", "account", "feedback", "partnership", "other"}:
            errors.append("Choose a contact topic.")
        if not values["message"] or len(values["message"]) > 5000:
            errors.append("Enter a message of up to 5,000 characters.")
        sent_attempt = not errors
        if sent_attempt:
            subjects = {
                "support": "Technical support",
                "account": "Account issues",
                "feedback": "Feedback and suggestions",
                "partnership": "Partnership inquiry",
                "other": "Other",
            }
            support_email = os.environ.get("SUPPORT_EMAIL", "support@gaminghub.com")
            try:
                send_email(
                    support_email,
                    f"Gaming Hub Contact: {subjects[values['subject']]}",
                    (
                        f"Name: {values['name']}\n"
                        f"Email: {values['email']}\n"
                        f"Topic: {subjects[values['subject']]}\n\n"
                        f"Message:\n{values['message']}\n"
                    ),
                    reply_to=values["email"],
                )
                delivered = True
                try:
                    send_email(
                        values["email"],
                        "Thanks for contacting Gaming Hub Support",
                        (
                            f"Hi {values['name']},\n\n"
                            "Thank you for contacting Gaming Hub Support. "
                            "We've received your message and will respond as soon "
                            "as possible.\n\n"
                            f"Your message:\n{values['message']}\n\n"
                            "The Gaming Hub Team"
                        ),
                    )
                except Exception:
                    current_app.logger.exception(
                        "Could not send contact form confirmation email"
                    )
                    delivery_error = (
                        "Your message was delivered to support, but the confirmation "
                        "email could not be sent."
                    )
            except EmailConfigurationError:
                current_app.logger.error(
                    "Contact form email is not configured; the message was not delivered"
                )
                delivery_error = (
                    "The message was not sent because outbound email is not configured. "
                    f"Please email {support_email} directly."
                )
            except Exception:
                current_app.logger.exception("Could not send contact form message")
                delivery_error = (
                    "The message could not be sent. Please try again later or email "
                    f"{support_email} directly."
                )
    return render_template(
        "stats/contact.html",
        errors=errors,
        values=values,
        sent_attempt=sent_attempt,
        delivery_error=delivery_error,
        delivered=delivered,
    )


@stats.get("/about/")
def about():
    return render_template("stats/about.html")


@stats.get("/terms/")
def terms():
    return render_template("stats/terms.html")


@stats.get("/privacy/")
def privacy():
    return render_template("stats/privacy.html")
