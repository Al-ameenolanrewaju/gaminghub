import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sqlite3
from datetime import datetime, timezone
from functools import wraps
from urllib.parse import urlsplit

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    g,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from itsdangerous import BadSignature, SignatureExpired, URLSafeTimedSerializer
from werkzeug.security import check_password_hash, generate_password_hash

from . import get_db
from .email import EmailConfigurationError, send_email, validate_email_configuration
from .game_rooms import catalog_game_id


auth_rooms = Blueprint("auth_rooms", __name__)

ROOM_GAMES = (
    "HUB_NEON_SPRINT",
    "HUB_CIPHER_CLASH",
    "HUB_TACTIC_GRID",
    "HUB_REACTION_RELAY",
    "DLS",
    "PES",
    "COD_MOBILE",
    "FREEFIRE",
    "PUBG_MOBILE",
    "FIFA",
    "COD",
    "FORTNITE",
    "VALORANT",
    "APEX",
    "MINECRAFT",
    "ROCKET_LEAGUE",
    "AMONG_US",
    "ROBLOX",
    "GTA",
    "NBA",
)
ROOM_SIZES = (2, 4, 6, 8, 10)
PREFERRED_MODES = ("CASUAL", "COMPETITIVE", "TOURNAMENT", "PRACTICE", "CUSTOM")
EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@auth_rooms.context_processor
def csrf_context():
    def csrf_token():
        token = session.get("csrf_token")
        if not token:
            token = secrets.token_urlsafe(32)
            session["csrf_token"] = token
        return token

    return {"csrf_token": csrf_token}


def _load_current_user():
    user_id = session.get("user_id")
    if not user_id:
        g.current_user = None
        return None
    g.current_user = get_db().execute(
        """
        SELECT id, username, password, email, first_name, last_name, is_active,
               is_staff, is_superuser, date_joined
        FROM auth_user
        WHERE id = ?
        """,
        (user_id,),
    ).fetchone()
    if g.current_user is None or not g.current_user["is_active"]:
        session.pop("user_id", None)
        g.current_user = None
    return g.current_user


def current_user():
    """Return the current request's auth_user row, if one is logged in."""
    return getattr(g, "current_user", None)


def _login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if _load_current_user() is None:
            flash("Please log in to continue.", "error")
            return redirect(url_for("auth_rooms.login", next=request.path))
        return view(*args, **kwargs)

    return wrapped


def _verify_password(encoded, password):
    """Verify PBKDF2-SHA256 and Werkzeug password hashes."""
    if not isinstance(encoded, str):
        return False
    if encoded.startswith("pbkdf2_sha256$"):
        try:
            algorithm, iterations, salt, expected = encoded.split("$", 3)
            if algorithm != "pbkdf2_sha256":
                return False
            actual = base64.b64encode(
                hashlib.pbkdf2_hmac(
                    "sha256", password.encode("utf-8"), salt.encode("utf-8"), int(iterations)
                )
            ).decode("ascii")
            return hmac.compare_digest(actual, expected)
        except (ValueError, TypeError, OverflowError):
            return False
    try:
        return check_password_hash(encoded, password)
    except (ValueError, TypeError):
        return False


def _start_authenticated_session(user_id):
    session.clear()
    session["user_id"] = user_id
    session["csrf_token"] = secrets.token_urlsafe(32)
    g.current_user = None


def _valid_email(email):
    return len(email) <= 254 and bool(EMAIL_RE.fullmatch(email))


def _safe_next_url(value):
    if not value or not value.startswith("/") or value.startswith("//") or "\\" in value:
        return None
    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        return None
    return value


def _room_code():
    alphabet = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
    database = get_db()
    while True:
        code = "".join(secrets.choice(alphabet) for _ in range(6))
        if database.execute(
            "SELECT 1 FROM core_room WHERE room_code = ?", (code,)
        ).fetchone() is None:
            return code


def _room_by_code(room_code):
    room = get_db().execute(
        """
        SELECT room.*, host.username AS host_username
        FROM core_room AS room
        JOIN auth_user AS host ON host.id = room.host_id
        WHERE room.room_code = ?
        """,
        (room_code,),
    ).fetchone()
    if room is None:
        abort(404)
    return room


def _ensure_profile(user_id):
    database = get_db()
    database.execute(
        """
        INSERT OR IGNORE INTO core_userprofile (
            bio, level, total_matches, win_rate, rank, country, platform, play_style,
            preferred_mode, date_joined, gamer_tag, main_game, avatar_color,
            show_online_status, show_match_history, allow_friend_requests,
            allow_messages, profile_visibility, total_score, verified_submissions,
            pending_submissions, last_submission, favorite_game_types, user_id
        ) VALUES (
            '', 1, 0, '0.00', NULL, '', '', '', 'COMPETITIVE', ?, '', '', '#3b82f6',
            1, 1, 1, 1, 'public', 0, 0, 0, NULL, '[]', ?
        )
        """,
        (datetime.now(timezone.utc).isoformat(), user_id),
    )
    return database.execute(
        "SELECT * FROM core_userprofile WHERE user_id = ?", (user_id,)
    ).fetchone()


@auth_rooms.route("/register/", methods=["GET", "POST"])
def register():
    errors = []
    values = {"username": "", "email": ""}
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")
        values.update(username=username, email=email)

        if not username or len(username) > 150:
            errors.append("Enter a username of 1 to 150 characters.")
        if not email or not _valid_email(email):
            errors.append("Enter a valid email address.")
        if len(password) < 8:
            errors.append("Password must contain at least 8 characters.")
        if password != password_confirm:
            errors.append("The passwords do not match.")

        database = get_db()
        if username and database.execute(
            "SELECT 1 FROM auth_user WHERE username = ? COLLATE NOCASE", (username,)
        ).fetchone():
            errors.append("That username is already in use.")

        if not errors:
            try:
                with database:
                    cursor = database.execute(
                        """
                        INSERT INTO auth_user (
                            password, last_login, is_superuser, username, last_name,
                            email, is_staff, is_active, date_joined, first_name
                        ) VALUES (?, NULL, 0, ?, '', ?, 0, 1, ?, '')
                        """,
                        (
                            generate_password_hash(password),
                            username,
                            email,
                            datetime.now(timezone.utc).isoformat(),
                        ),
                    )
                    user_id = cursor.lastrowid
                    _ensure_profile(user_id)
            except sqlite3.IntegrityError:
                errors.append("An account with those details already exists.")
            else:
                _start_authenticated_session(user_id)
                try:
                    send_email(
                        email,
                        "Welcome to Gaming Hub",
                        f"Hello {username},\n\nWelcome to Gaming Hub. Your account is ready.\n",
                    )
                except EmailConfigurationError:
                    flash(
                        "Your account is ready. Welcome email was not sent because "
                        "outbound email is not configured.",
                        "warning",
                    )
                except Exception:
                    current_app.logger.exception("Could not send welcome email")
                    flash(
                        "Your account is ready, but the welcome email could not be sent.",
                        "warning",
                    )
                else:
                    flash("Your account is ready. Welcome to Gaming Hub!", "success")
                return redirect(url_for("main.home"))

    return render_template("auth/register.html", errors=errors, values=values)


@auth_rooms.route("/login/", methods=["GET", "POST"])
def login():
    errors = []
    username = ""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = get_db().execute(
            """
            SELECT id, username, password, email, is_active FROM auth_user
            WHERE username = ? COLLATE NOCASE
            """,
            (username,),
        ).fetchone()
        if user is None or not user["is_active"] or not _verify_password(
            user["password"], password
        ):
            errors.append("The username or password is incorrect.")
        else:
            _start_authenticated_session(user["id"])
            admin_email = os.environ.get("ADMIN_EMAIL", "").strip()
            if admin_email and user["email"]:
                try:
                    send_email(
                        admin_email,
                        "ADMIN: User Logged In",
                        f"User {user['username']} logged in from IP: "
                        f"{request.remote_addr or 'unknown'}",
                    )
                except EmailConfigurationError:
                    flash(
                        "You are logged in, but the admin login notification was not "
                        "sent because outbound email is not configured.",
                        "warning",
                    )
                except Exception:
                    current_app.logger.exception(
                        "Could not send admin login notification"
                    )
                    flash(
                        "You are logged in, but the admin login notification could "
                        "not be sent.",
                        "warning",
                    )
            flash("You are now logged in.", "success")
            next_url = _safe_next_url(request.args.get("next"))
            if next_url:
                return redirect(next_url)
            return redirect(url_for("auth_rooms.room_list"))
    return render_template("auth/login.html", errors=errors, username=username)


@auth_rooms.post("/logout/")
@_login_required
def logout():
    session.clear()
    g.current_user = None
    flash("You have been logged out.", "success")
    return redirect(url_for("auth_rooms.login"))


@auth_rooms.get("/profile/<string:username>/")
def profile(username):
    database = get_db()
    profile_user = database.execute(
        """
        SELECT id, username, email, first_name, last_name, date_joined
        FROM auth_user WHERE username = ?
        """,
        (username,),
    ).fetchone()
    if profile_user is None:
        abort(404)
    profile_data = database.execute(
        "SELECT * FROM core_userprofile WHERE user_id = ?", (profile_user["id"],)
    ).fetchone()
    own_profile = _load_current_user()
    own_profile = own_profile is not None and own_profile["id"] == profile_user["id"]
    if (
        profile_data is not None
        and profile_data["profile_visibility"] != "public"
        and not own_profile
    ):
        abort(404)
    return render_template(
        "auth/profile.html",
        profile_user=profile_user,
        profile_data=profile_data,
        own_profile=own_profile,
    )


@auth_rooms.route("/profile/edit/,", methods=["GET", "POST"])
@auth_rooms.route("/profile/edit/", methods=["GET", "POST"])
@_login_required
def edit_profile():
    user_row = _load_current_user()
    profile_data = _ensure_profile(user_row["id"])
    errors = []
    values = dict(profile_data)
    values["email"] = user_row["email"]

    if request.method == "POST":
        email = request.form.get("email", "").strip()
        bio = request.form.get("bio", "").strip()
        country = request.form.get("country", "").strip()
        platform = request.form.get("platform", "").strip()
        play_style = request.form.get("play_style", "").strip()
        gamer_tag = request.form.get("gamer_tag", "").strip()
        main_game = request.form.get("main_game", "").strip()
        preferred_mode = request.form.get("preferred_mode", "COMPETITIVE").strip()
        profile_visibility = request.form.get("profile_visibility", "public").strip()
        values.update(
            email=email,
            bio=bio,
            country=country,
            platform=platform,
            play_style=play_style,
            gamer_tag=gamer_tag,
            main_game=main_game,
            preferred_mode=preferred_mode,
            profile_visibility=profile_visibility,
        )

        if not _valid_email(email):
            errors.append("Enter a valid email address.")
        for label, value, limit in (
            ("Bio", bio, 500),
            ("Country", country, 100),
            ("Platform", platform, 100),
            ("Play style", play_style, 100),
            ("Gamer tag", gamer_tag, 100),
            ("Main game", main_game, 100),
        ):
            if len(value) > limit:
                errors.append(f"{label} must be {limit} characters or fewer.")
        if preferred_mode not in PREFERRED_MODES:
            errors.append("Choose a valid preferred play mode.")
        if profile_visibility not in ("public", "friends", "private"):
            errors.append("Choose a valid profile visibility setting.")

        if not errors:
            with get_db() as database:
                database.execute(
                    """
                    UPDATE auth_user SET email = ? WHERE id = ?
                    """,
                    (email, user_row["id"]),
                )
                database.execute(
                    """
                    UPDATE core_userprofile
                    SET bio = ?, country = ?, platform = ?, play_style = ?,
                        gamer_tag = ?, main_game = ?, preferred_mode = ?,
                        profile_visibility = ?
                    WHERE user_id = ?
                    """,
                    (
                        bio,
                        country,
                        platform,
                        play_style,
                        gamer_tag,
                        main_game,
                        preferred_mode,
                        profile_visibility,
                        user_row["id"],
                    ),
                )
            flash("Your profile has been updated.", "success")
            return redirect(
                url_for("auth_rooms.profile", username=user_row["username"])
            )
    return render_template("auth/edit_profile.html", errors=errors, values=values)


@auth_rooms.route("/test-profile/", methods=["GET", "POST"])
@_login_required
def test_profile():
    user_row = _load_current_user()
    profile_data = _ensure_profile(user_row["id"])
    games = get_db().execute(
        "SELECT id, name FROM core_game ORDER BY name"
    ).fetchall()
    try:
        selected_ids = json.loads(profile_data["favorite_game_types"] or "[]")
    except (TypeError, json.JSONDecodeError):
        selected_ids = []
    if not isinstance(selected_ids, list):
        selected_ids = []

    if request.method == "POST":
        game_ids = set()
        for value in request.form.getlist("favorite_game_ids"):
            try:
                game_ids.add(int(value))
            except ValueError:
                continue
        selected = [
            row["name"]
            for row in games
            if row["id"] in game_ids
        ][:5]
        with get_db() as database:
            database.execute(
                "UPDATE core_userprofile SET favorite_game_types = ? WHERE user_id = ?",
                (json.dumps(selected), user_row["id"]),
            )
        flash("Your favorite games were updated.", "success")
        return redirect(url_for("auth_rooms.test_profile"))

    return render_template(
        "auth/test_profile.html",
        games=games,
        selected_ids=selected_ids,
    )


@auth_rooms.get("/rooms/")
def room_list():
    user_row = _load_current_user()
    rooms = get_db().execute(
        """
        SELECT room.id, room.title, room.description, room.game, room.room_code,
               room.max_players, room.is_active, room.status, room.created_at,
               host.username AS host_username,
               (SELECT COUNT(*) FROM core_room_players AS players
                WHERE players.room_id = room.id) + 1 AS current_players,
               CASE WHEN ? IS NOT NULL AND EXISTS (
                   SELECT 1 FROM core_room_players AS mine
                   WHERE mine.room_id = room.id AND mine.user_id = ?
               ) THEN 1 ELSE 0 END AS joined
        FROM core_room AS room
        JOIN auth_user AS host ON host.id = room.host_id
        WHERE room.is_active = 1
        ORDER BY room.created_at DESC
        """,
        (user_row["id"] if user_row else None, user_row["id"] if user_row else None),
    ).fetchall()
    return render_template("rooms/list.html", rooms=rooms)


@auth_rooms.route("/rooms/create/", methods=["GET", "POST"])
@_login_required
def create_room():
    errors = []
    values = {
        "title": "",
        "description": "",
        "game": "",
        "max_players": "4",
        "game_password": "",
    }
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        game = request.form.get("game", "").strip()
        game_password = request.form.get("game_password", "").strip()
        values.update(
            title=title,
            description=description,
            game=game,
            max_players=request.form.get("max_players", ""),
            game_password="",
        )
        try:
            max_players = int(values["max_players"])
        except (TypeError, ValueError):
            max_players = 0

        if not title or len(title) > 100:
            errors.append("Room title is required and must be at most 100 characters.")
        if len(description) > 500:
            errors.append("Description must be at most 500 characters.")
        if game not in ROOM_GAMES:
            errors.append("Choose a valid game.")
        if max_players not in ROOM_SIZES:
            errors.append("Choose a room capacity of 2, 4, 6, 8, or 10 players.")
        if game == "HUB_TACTIC_GRID" and max_players != 2:
            errors.append("Tactic Grid rooms must be limited to exactly two players.")
        if game_password and not 4 <= len(game_password) <= 10:
            errors.append("Room password must be 4 to 10 characters.")

        if not errors:
            user_row = _load_current_user()
            database = get_db()
            code = _room_code()
            with database:
                cursor = database.execute(
                    """
                    INSERT INTO core_room (
                        title, description, game, is_active, created_at, host_id,
                        game_password, room_code, status, max_players
                    ) VALUES (?, ?, ?, 1, ?, ?, ?, ?, 'waiting', ?)
                    """,
                    (
                        title,
                        description,
                        game,
                        datetime.now(timezone.utc).isoformat(),
                        user_row["id"],
                        game_password or None,
                        code,
                        max_players,
                    ),
                )
                room_id = cursor.lastrowid
                game_id = catalog_game_id(database, game)
                if game_id is not None:
                    database.execute(
                        "INSERT OR IGNORE INTO core_game_rooms (game_id, room_id) VALUES (?, ?)",
                        (game_id, room_id),
                    )
            flash(f"Room created. Share code {code} with other players.", "success")
            if user_row["email"] and game not in {
                "HUB_NEON_SPRINT",
                "HUB_CIPHER_CLASH",
                "HUB_TACTIC_GRID",
                "HUB_REACTION_RELAY",
            }:
                try:
                    send_email(
                        user_row["email"],
                        f"Gaming Hub room created: {title}",
                        (
                            f"Hello {user_row['username']},\n\n"
                            f'Your {game} room "{title}" is ready.\n'
                            f"Room code: {code}\n"
                            "Share this code with the players you want to invite."
                        ),
                    )
                except EmailConfigurationError:
                    flash(
                        "The room was created, but the host notification email was "
                        "not sent because outbound email is not configured.",
                        "warning",
                    )
                except Exception:
                    current_app.logger.exception("Could not send room creation email")
                    flash(
                        "The room was created, but its host notification email could "
                        "not be sent.",
                        "warning",
                    )
            return redirect(url_for("auth_rooms.room_detail", room_code=code))
    return render_template(
        "rooms/create.html", errors=errors, values=values, games=ROOM_GAMES, sizes=ROOM_SIZES
    )


@auth_rooms.get("/rooms/<string:room_code>/")
def room_detail(room_code):
    room = _room_by_code(room_code)
    database = get_db()
    participants = database.execute(
        """
        SELECT user.id, user.username, 1 AS is_host
        FROM auth_user AS user
        WHERE user.id = ?
        UNION ALL
        SELECT user.id, user.username, 0 AS is_host
        FROM core_room_players AS players
        JOIN auth_user AS user ON user.id = players.user_id
        WHERE players.room_id = ?
        ORDER BY is_host DESC, username
        """,
        (room["host_id"], room["id"]),
    ).fetchall()
    current = _load_current_user()
    is_joined = current is not None and database.execute(
        """
        SELECT 1 FROM core_room_players WHERE room_id = ? AND user_id = ?
        """,
        (room["id"], current["id"]),
    ).fetchone() is not None
    is_host = current is not None and current["id"] == room["host_id"]
    return render_template(
        "rooms/detail.html",
        room=room,
        participants=participants,
        is_joined=is_joined,
        is_host=is_host,
        is_full=len(participants) >= room["max_players"],
    )


@auth_rooms.post("/rooms/<string:room_code>/join/")
@_login_required
def join_room(room_code):
    room = _room_by_code(room_code)
    user_row = _load_current_user()
    database = get_db()
    if not room["is_active"]:
        flash("This room is no longer active.", "error")
    elif user_row["id"] == room["host_id"]:
        flash("You are already the host of this room.", "info")
    elif database.execute(
        "SELECT 1 FROM core_room_players WHERE room_id = ? AND user_id = ?",
        (room["id"], user_row["id"]),
    ).fetchone():
        flash("You have already joined this room.", "info")
    elif room["game"] == "HUB_TACTIC_GRID" and database.execute(
        "SELECT COUNT(*) FROM core_room_players WHERE room_id = ?", (room["id"],)
    ).fetchone()[0] >= 1:
        flash("Tactic Grid rooms are limited to two players.", "error")
    elif not hmac.compare_digest(
        request.form.get("game_password", ""), room["game_password"] or ""
    ):
        flash("The room password is incorrect.", "error")
    else:
        current_players = database.execute(
            "SELECT COUNT(*) FROM core_room_players WHERE room_id = ?", (room["id"],)
        ).fetchone()[0] + 1
        if current_players >= room["max_players"]:
            flash("This room is full.", "error")
        else:
            with database:
                database.execute(
                    "INSERT INTO core_room_players (room_id, user_id) VALUES (?, ?)",
                    (room["id"], user_row["id"]),
                )
                if current_players + 1 >= room["max_players"]:
                    database.execute(
                        "UPDATE core_room SET status = 'full' WHERE id = ?", (room["id"],)
                    )
            flash("You joined the room.", "success")
    return redirect(url_for("auth_rooms.room_detail", room_code=room_code))


@auth_rooms.post("/rooms/<string:room_code>/leave/")
@_login_required
def leave_room(room_code):
    room = _room_by_code(room_code)
    user_row = _load_current_user()
    if user_row["id"] == room["host_id"]:
        flash("The room host cannot leave; deactivate or close the room instead.", "error")
    else:
        with get_db() as database:
            cursor = database.execute(
                "DELETE FROM core_room_players WHERE room_id = ? AND user_id = ?",
                (room["id"], user_row["id"]),
            )
            if cursor.rowcount:
                database.execute(
                    "UPDATE core_room SET status = 'waiting' WHERE id = ? AND status = 'full'",
                    (room["id"],),
                )
                flash("You left the room.", "success")
            else:
                flash("You are not a member of this room.", "info")
    return redirect(url_for("auth_rooms.room_list"))


def _password_reset_serializer():
    return URLSafeTimedSerializer(
        current_app.config["SECRET_KEY"], salt="gaming-hub-password-reset"
    )


def _password_reset_token(user):
    return _password_reset_serializer().dumps(
        {"user_id": user["id"], "password_hash": user["password"]}
    )


def _password_reset_user(uidb64, token):
    try:
        user_id = int(base64.urlsafe_b64decode(uidb64 + "=" * (-len(uidb64) % 4)))
        payload = _password_reset_serializer().loads(token, max_age=3600)
    except (ValueError, TypeError, BadSignature, SignatureExpired):
        return None
    if not isinstance(payload, dict) or payload.get("user_id") != user_id:
        return None
    user = get_db().execute(
        "SELECT id, username, password, is_active FROM auth_user WHERE id = ?",
        (user_id,),
    ).fetchone()
    if (
        user is None
        or not user["is_active"]
        or not isinstance(payload.get("password_hash"), str)
        or not hmac.compare_digest(user["password"], payload["password_hash"])
    ):
        return None
    return user


def _reset_uid(user_id):
    return base64.urlsafe_b64encode(str(user_id).encode("ascii")).decode("ascii").rstrip("=")


@auth_rooms.route("/password-reset/", methods=["GET", "POST"])
def password_reset():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        if not _valid_email(email):
            flash("Enter a valid email address.", "error")
            return render_template("auth/reset.html")

        public_base_url = current_app.config.get("PUBLIC_BASE_URL") or os.environ.get(
            "PUBLIC_BASE_URL"
        )
        try:
            parsed_base_url = urlsplit(public_base_url or "")
            base_url_is_valid = (
                parsed_base_url.scheme == "https"
                and bool(parsed_base_url.netloc)
                and not parsed_base_url.username
                and not parsed_base_url.password
                and not parsed_base_url.query
                and not parsed_base_url.fragment
            )
        except (TypeError, ValueError):
            base_url_is_valid = False
        if not base_url_is_valid:
            current_app.logger.error(
                "Password reset requested without a valid HTTPS PUBLIC_BASE_URL"
            )
            flash(
                "Password reset email is not configured. Set PUBLIC_BASE_URL to the "
                "canonical HTTPS site URL, or contact support.",
                "error",
            )
            return render_template("auth/reset.html")
        try:
            validate_email_configuration()
        except EmailConfigurationError:
            current_app.logger.error(
                "Password reset requested without configured outbound email"
            )
            flash(
                "Password reset email is not configured. Configure outbound email "
                "or contact support.",
                "error",
            )
            return render_template("auth/reset.html")

        user = get_db().execute(
            "SELECT id, username, email, password FROM auth_user WHERE email = ? COLLATE NOCASE AND is_active = 1",
            (email,),
        ).fetchone()
        if user is not None:
            reset_url = (
                f"{public_base_url.rstrip('/')}"
                f"{url_for('auth_rooms.password_reset_confirm', uidb64=_reset_uid(user['id']), token=_password_reset_token(user))}"
            )
            try:
                send_email(
                    email,
                    "Reset your Gaming Hub password",
                    "We received a request to reset your password. This link expires in "
                    f"one hour and can only be used once:\n\n{reset_url}\n\n"
                    "If you did not request this, you can ignore this email.",
                )
            except EmailConfigurationError:
                current_app.logger.error(
                    "Password reset requested but outbound email is not configured"
                )
                return redirect(url_for("auth_rooms.password_reset_done"))
            except Exception:
                current_app.logger.exception("Could not send password reset email")
                return redirect(url_for("auth_rooms.password_reset_done"))

        return redirect(url_for("auth_rooms.password_reset_done"))
    return render_template("auth/reset.html")


@auth_rooms.get("/password-reset/done/")
def password_reset_done():
    return render_template("auth/reset_done.html")


@auth_rooms.route(
    "/password-reset-confirm/<string:uidb64>/<string:token>/",
    methods=["GET", "POST"],
)
def password_reset_confirm(uidb64, token):
    user = _password_reset_user(uidb64, token)
    if user is None:
        return render_template(
            "auth/reset_confirm.html",
            errors=["This password reset link is invalid or has expired."],
            valid=False,
        ), 400

    errors = []
    if request.method == "POST":
        password = request.form.get("password", "")
        confirm_password = request.form.get("password_confirm", "")
        if len(password) < 8:
            errors.append("Password must contain at least 8 characters.")
        if password != confirm_password:
            errors.append("The passwords do not match.")
        if not errors:
            database = get_db()
            cursor = database.execute(
                "UPDATE auth_user SET password = ? WHERE id = ? AND password = ?",
                (
                    generate_password_hash(password),
                    user["id"],
                    user["password"],
                ),
            )
            database.commit()
            if cursor.rowcount != 1:
                errors.append("This password reset link has already been used.")
            else:
                return redirect(url_for("auth_rooms.password_reset_complete"))
    return render_template("auth/reset_confirm.html", errors=errors, valid=True)


@auth_rooms.get("/password-reset-complete/")
def password_reset_complete():
    return render_template("auth/reset_complete.html")
