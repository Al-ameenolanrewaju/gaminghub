"""Tournament and Clash Royale routes for the Flask application."""

import json
import os
import random
import re
import sqlite3
import urllib.error
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from functools import wraps
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

from . import PROJECT_ROOT, get_db


competitions = Blueprint("competitions", __name__)

PAYMENT_METHODS = {"bank_transfer", "mobile_money", "crypto", "cash", "other"}
MAX_PAYMENT_PROOF_SIZE = 10 * 1024 * 1024
PAYMENT_PROOF_FORMATS = {
    ".jpg": ("JPEG", ".jpg"),
    ".jpeg": ("JPEG", ".jpg"),
    ".png": ("PNG", ".png"),
    ".gif": ("GIF", ".gif"),
    ".webp": ("WEBP", ".webp"),
    ".pdf": ("PDF", ".pdf"),
}


def _current_user():
    """Resolve the session identity against existing user records."""
    user_id = session.get("user_id")
    if user_id is None:
        return None
    try:
        user_id = int(user_id)
    except (TypeError, ValueError):
        session.pop("user_id", None)
        return None
    database = get_db()
    columns = {
        column["name"]
        for column in database.execute("PRAGMA table_info(auth_user)").fetchall()
    }
    active_filter = " AND is_active = 1" if "is_active" in columns else ""
    selected = ["id", "username"]
    if "email" in columns:
        selected.append("email")
    user = database.execute(
        f"SELECT {', '.join(selected)} FROM auth_user WHERE id = ?{active_filter}",
        (user_id,),
    ).fetchone()
    if user is None:
        session.pop("user_id", None)
    return user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if _current_user() is None:
            flash("Please log in to continue.", "error")
            return redirect("/login/?next=" + quote(request.full_path.rstrip("?")))
        return view(*args, **kwargs)

    return wrapped


def _tournament_or_404(tournament_id):
    row = get_db().execute(
        """
        SELECT t.*, g.name AS game_name
        FROM tournament_tournament AS t
        LEFT JOIN tournament_game AS g ON g.id = t.game_id
        WHERE t.id = ?
        """,
        (tournament_id,),
    ).fetchone()
    if row is None:
        abort(404)
    return row


def _registration_open(database, tournament):
    now = datetime.now(timezone.utc)
    try:
        starts = _as_utc(tournament["start_date"])
        deadline = _as_utc(tournament["registration_deadline"])
    except (KeyError, TypeError, ValueError):
        return False
    return (
        tournament["status"] == "upcoming"
        and now < starts
        and now < deadline
        and int(tournament["current_participants"] or 0)
        < int(tournament["max_participants"] or 0)
    )


def _as_utc(value):
    parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _reserved_subscriptions(database, tournament_id):
    row = database.execute(
        """
        SELECT COUNT(*) AS total
        FROM tournament_tournamentsubscription
        WHERE tournament_id = ? AND payment_status IN ('pending', 'processing')
        """,
        (tournament_id,),
    ).fetchone()
    return int(row["total"])


def _registration_error(database, tournament):
    if tournament["status"] != "upcoming":
        return "Registration is closed for this tournament."
    try:
        if datetime.now(timezone.utc) >= _as_utc(tournament["start_date"]):
            return "Registration is closed because the tournament has started."
        if datetime.now(timezone.utc) >= _as_utc(tournament["registration_deadline"]):
            return "The registration deadline has passed."
    except (TypeError, ValueError):
        return "Registration dates are invalid; contact the tournament organizer."
    occupied = int(tournament["current_participants"] or 0)
    occupied += _reserved_subscriptions(database, tournament["id"])
    if occupied >= int(tournament["max_participants"] or 0):
        return "This tournament is full."
    return None


def _defaults_for_rewards(tournament):
    prize = Decimal(str(tournament["game_prize"] or 0))
    return [
        {
            "position": position,
            "reward_amount": (prize * share).quantize(Decimal("0.01")),
            "reward_description": label,
        }
        for position, share, label in (
            (1, Decimal("0.50"), "First Place"),
            (2, Decimal("0.30"), "Second Place"),
            (3, Decimal("0.20"), "Third Place"),
        )
    ]


def _save_payment_proof(upload):
    if upload is None or not upload.filename:
        return None, None

    safe_name = secure_filename(upload.filename)
    expected = PAYMENT_PROOF_FORMATS.get(Path(safe_name).suffix.lower())
    if not safe_name or expected is None:
        return None, "Choose a PDF, PNG, JPEG, GIF, or WebP payment proof."

    upload.stream.seek(0, 2)
    size = upload.stream.tell()
    upload.stream.seek(0)
    if size <= 0 or size > MAX_PAYMENT_PROOF_SIZE:
        return None, "Payment proof must be a non-empty file of 10 MB or less."

    try:
        if expected[0] == "PDF":
            if not upload.stream.read(5).startswith(b"%PDF-"):
                return None, "The selected file is not a valid PDF."
        else:
            image = Image.open(upload.stream)
            if image.format != expected[0] or image.width * image.height > 40_000_000:
                return None, "The image format or dimensions are not supported."
            image.verify()
    except (
        UnidentifiedImageError,
        OSError,
        ValueError,
        SyntaxError,
        Image.DecompressionBombError,
    ):
        return None, "The selected payment proof is not a valid supported file."
    finally:
        upload.stream.seek(0)

    relative_path = Path("payment_proofs") / datetime.now(timezone.utc).strftime("%Y/%m/%d")
    stored_path = relative_path / f"{uuid4().hex}{expected[1]}"
    media_root = Path(current_app.config.get("MEDIA_ROOT", PROJECT_ROOT / "media"))
    destination = media_root / stored_path
    destination.parent.mkdir(parents=True, exist_ok=True)
    upload.save(destination)
    return stored_path.as_posix(), None


@competitions.get("/tournament/")
def tournament_list():
    tournaments = get_db().execute(
        """
        SELECT t.id, t.title, t.description, t.status, t.format, t.start_date,
               t.registration_deadline, t.entry_fee, t.game_prize, t.currency,
               t.max_participants, t.current_participants, t.banner_image,
               g.name AS game_name
        FROM tournament_tournament AS t
        LEFT JOIN tournament_game AS g ON g.id = t.game_id
        ORDER BY t.start_date DESC, t.id DESC
        """
    ).fetchall()
    return render_template("competitions/tournament_list.html", tournaments=tournaments)


@competitions.get("/tournament/<int:tournament_id>/")
def tournament_detail(tournament_id):
    tournament = _tournament_or_404(tournament_id)
    database = get_db()
    user = _current_user()
    subscription = None
    if user is not None:
        subscription = database.execute(
            """
            SELECT id, payment_status
            FROM tournament_tournamentsubscription
            WHERE user_id = ? AND tournament_id = ?
            """,
            (user["id"], tournament_id),
        ).fetchone()
    return render_template(
        "competitions/tournament_detail.html",
        tournament=tournament,
        rewards=_defaults_for_rewards(tournament),
        is_subscribed=subscription is not None,
        user_subscription=subscription,
        registration_open=_registration_open(database, tournament),
    )


@competitions.route("/tournament/<int:tournament_id>/subscribe/", methods=["GET", "POST"])
@login_required
def subscribe_tournament(tournament_id):
    tournament = _tournament_or_404(tournament_id)
    database = get_db()
    user = _current_user()
    existing = database.execute(
        """
        SELECT id, payment_status FROM tournament_tournamentsubscription
        WHERE user_id = ? AND tournament_id = ?
        """,
        (user["id"], tournament_id),
    ).fetchone()
    if existing is not None:
        flash("You already have a registration for this tournament.", "info")
        if existing["payment_status"] in ("pending", "processing"):
            return redirect(
                url_for(
                    "competitions.payment_status",
                    subscription_id=existing["id"],
                )
            )
        return redirect(url_for("competitions.tournament_detail", tournament_id=tournament_id))
    error = _registration_error(database, tournament)
    if error:
        flash(error, "error")
        return redirect(url_for("competitions.tournament_detail", tournament_id=tournament_id))
    return redirect(url_for("competitions.tournament_payment", tournament_id=tournament_id))


@competitions.get("/tournament/<int:tournament_id>/payment/")
@login_required
def tournament_payment(tournament_id):
    tournament = _tournament_or_404(tournament_id)
    user = _current_user()
    database = get_db()
    existing = database.execute(
        """
        SELECT id FROM tournament_tournamentsubscription
        WHERE user_id = ? AND tournament_id = ?
        """,
        (user["id"], tournament_id),
    ).fetchone()
    if existing is not None:
        return redirect(
            url_for("competitions.payment_status", subscription_id=existing["id"])
        )
    error = _registration_error(database, tournament)
    if error:
        flash(error, "error")
        return redirect(url_for("competitions.tournament_detail", tournament_id=tournament_id))
    return render_template("competitions/payment.html", tournament=tournament)


@competitions.route(
    "/tournament/<int:tournament_id>/payment/submit/", methods=["GET", "POST"]
)
@login_required
def submit_payment(tournament_id):
    if request.method == "GET":
        return redirect(
            url_for("competitions.tournament_payment", tournament_id=tournament_id)
        )
    database = get_db()
    user = _current_user()
    payment_proof = None
    try:
        database.execute("BEGIN IMMEDIATE")
        tournament = _tournament_or_404(tournament_id)
        existing = database.execute(
            """
            SELECT id, payment_status FROM tournament_tournamentsubscription
            WHERE user_id = ? AND tournament_id = ?
            """,
            (user["id"], tournament_id),
        ).fetchone()
        if existing is not None and existing["payment_status"] not in ("failed", "refunded"):
            database.rollback()
            flash("A registration already exists for this tournament.", "info")
            return redirect(
                url_for("competitions.payment_status", subscription_id=existing["id"])
            )
        error = _registration_error(database, tournament)
        if error and existing is None:
            database.rollback()
            flash(error, "error")
            return redirect(
                url_for("competitions.tournament_detail", tournament_id=tournament_id)
            )

        method = request.form.get("payment_method", "mobile_money").strip()
        if method not in PAYMENT_METHODS:
            database.rollback()
            flash("Choose a valid payment method.", "error")
            return redirect(
                url_for("competitions.tournament_payment", tournament_id=tournament_id)
            )

        transaction_id = request.form.get("transaction_id", "").strip()[:100] or None
        payer_name = request.form.get("payer_name", "").strip()[:255] or user["username"]
        user_email = user["email"] if "email" in user.keys() else ""
        payer_email = request.form.get("payer_email", "").strip()[:254] or user_email
        if payer_email and not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", payer_email):
            database.rollback()
            flash("Enter a valid payer email address.", "error")
            return redirect(
                url_for("competitions.tournament_payment", tournament_id=tournament_id)
            )
        payment_proof, proof_error = _save_payment_proof(
            request.files.get("payment_proof")
        )
        if proof_error:
            database.rollback()
            flash(proof_error, "error")
            return redirect(
                url_for("competitions.tournament_payment", tournament_id=tournament_id)
            )
        amount = str(Decimal(str(tournament["entry_fee"] or 0)).quantize(Decimal("0.01")))
        submitted_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        if existing is not None:
            subscription_id = existing["id"]
            database.execute(
                """
                UPDATE tournament_tournamentsubscription
                SET subscription_date = ?, transaction_id = ?, admin_notes = NULL,
                    payer_email = ?, payer_name = ?, payer_phone = NULL,
                    payment_amount = ?, payment_date = NULL,
                    payment_method = ?, payment_proof = ?,
                    verified_at = NULL, verified_by_id = NULL, payment_status = 'pending'
                WHERE id = ? AND user_id = ?
                """,
                (
                    submitted_at,
                    transaction_id,
                    payer_email,
                    payer_name,
                    amount,
                    method,
                    payment_proof,
                    subscription_id,
                    user["id"],
                ),
            )
        else:
            cursor = database.execute(
                """
                INSERT INTO tournament_tournamentsubscription
                    (subscription_date, transaction_id, tournament_id, user_id,
                     payment_amount, payment_method, payment_status,
                     payer_name, payer_email, payment_proof)
                VALUES (?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)
                """,
                (
                    submitted_at,
                    transaction_id,
                    tournament_id,
                    user["id"],
                    amount,
                    method,
                    payer_name,
                    payer_email,
                    payment_proof,
                ),
            )
            subscription_id = cursor.lastrowid
        database.commit()
    except (sqlite3.IntegrityError, InvalidOperation):
        database.rollback()
        if payment_proof:
            (Path(current_app.config.get("MEDIA_ROOT", PROJECT_ROOT / "media")) / payment_proof).unlink(missing_ok=True)
        flash("Could not register this payment. Check the tournament and try again.", "error")
        return redirect(
            url_for("competitions.tournament_payment", tournament_id=tournament_id)
        )
    except Exception:
        database.rollback()
        if payment_proof:
            (Path(current_app.config.get("MEDIA_ROOT", PROJECT_ROOT / "media")) / payment_proof).unlink(missing_ok=True)
        raise
    flash(
        "Payment details were recorded as pending. This Flask port cannot verify or "
        "process payments; a tournament administrator must confirm payment separately.",
        "warning",
    )
    return redirect(
        url_for("competitions.payment_status", subscription_id=subscription_id)
    )


@competitions.get("/tournament/my-tournaments/")
@login_required
def user_tournaments():
    database = get_db()
    user = _current_user()
    subscriptions = database.execute(
        """
        SELECT s.id AS subscription_id, s.payment_status, s.payment_amount,
               t.id, t.title, t.status, t.start_date, t.end_date, t.currency
        FROM tournament_tournamentsubscription AS s
        JOIN tournament_tournament AS t ON t.id = s.tournament_id
        WHERE s.user_id = ?
        ORDER BY s.subscription_date DESC
        """,
        (user["id"],),
    ).fetchall()
    return render_template("competitions/my_tournaments.html", subscriptions=subscriptions)


@competitions.get("/tournament/<int:tournament_id>/results/")
def tournament_results(tournament_id):
    tournament = _tournament_or_404(tournament_id)
    if tournament["status"] != "completed":
        return render_template(
            "competitions/results.html",
            tournament=tournament,
            not_completed=True,
            result=None,
            completed_matches=[],
            rewards=_defaults_for_rewards(tournament),
        )
    database = get_db()
    result = database.execute(
        """
        SELECT r.*, first.username AS first_username,
               second.username AS second_username, third.username AS third_username
        FROM tournament_tournamentresult AS r
        LEFT JOIN auth_user AS first ON first.id = r.first_place_id
        LEFT JOIN auth_user AS second ON second.id = r.second_place_id
        LEFT JOIN auth_user AS third ON third.id = r.third_place_id
        WHERE r.tournament_id = ?
        """,
        (tournament_id,),
    ).fetchone()
    completed_matches = _get_matches(database, tournament_id, completed_only=True)
    standings = []
    if result:
        try:
            standings = json.loads(result["final_standings"] or "[]")
            if not isinstance(standings, list):
                standings = []
        except (TypeError, json.JSONDecodeError):
            standings = []
        user_ids = {
            standing.get("user_id")
            for standing in standings
            if isinstance(standing, dict) and standing.get("user_id") is not None
        }
        if user_ids:
            placeholders = ", ".join("?" for _ in user_ids)
            names = {
                row["id"]: row["username"]
                for row in database.execute(
                    f"SELECT id, username FROM auth_user WHERE id IN ({placeholders})",
                    tuple(user_ids),
                ).fetchall()
            }
            for standing in standings:
                if isinstance(standing, dict):
                    standing["username"] = names.get(standing.get("user_id"), "Unknown")
    return render_template(
        "competitions/results.html",
        tournament=tournament,
        not_completed=False,
        result=result,
        standings=standings,
        completed_matches=completed_matches,
        rewards=_defaults_for_rewards(tournament),
    )


def _get_matches(database, tournament_id, completed_only=False):
    status_clause = "AND m.status = 'completed'" if completed_only else ""
    return database.execute(
        f"""
        SELECT m.id, m.round_number, m.match_number, m.scheduled_time, m.status,
               m.score_player1, m.score_player2,
               p1.username AS player1_username, p2.username AS player2_username,
               winner.username AS winner_username
        FROM tournament_match AS m
        LEFT JOIN auth_user AS p1 ON p1.id = m.player1_id
        LEFT JOIN auth_user AS p2 ON p2.id = m.player2_id
        LEFT JOIN auth_user AS winner ON winner.id = m.winner_id
        WHERE m.tournament_id = ? {status_clause}
        ORDER BY m.round_number, m.match_number
        """,
        (tournament_id,),
    ).fetchall()


@competitions.get("/tournament/<int:tournament_id>/match-results/")
def match_results(tournament_id):
    tournament = _tournament_or_404(tournament_id)
    return render_template(
        "competitions/match_results.html",
        tournament=tournament,
        matches=_get_matches(get_db(), tournament_id),
    )


@competitions.get("/tournament/payment/status/<int:subscription_id>/")
@login_required
def payment_status(subscription_id):
    user = _current_user()
    subscription = get_db().execute(
        """
        SELECT s.*, t.title AS tournament_title, t.currency
        FROM tournament_tournamentsubscription AS s
        JOIN tournament_tournament AS t ON t.id = s.tournament_id
        WHERE s.id = ? AND s.user_id = ?
        """,
        (subscription_id, user["id"]),
    ).fetchone()
    if subscription is None:
        abort(404)
    return render_template("competitions/payment_status.html", subscription=subscription)


@competitions.get("/tournament/payment/history/")
@login_required
def user_payment_history():
    user = _current_user()
    subscriptions = get_db().execute(
        """
        SELECT s.id, s.subscription_date, s.payment_status, s.payment_method,
               s.payment_amount, s.transaction_id, t.id AS tournament_id,
               t.title AS tournament_title, t.currency
        FROM tournament_tournamentsubscription AS s
        JOIN tournament_tournament AS t ON t.id = s.tournament_id
        WHERE s.user_id = ?
        ORDER BY s.subscription_date DESC
        """,
        (user["id"],),
    ).fetchall()
    return render_template(
        "competitions/payment_history.html", subscriptions=subscriptions
    )


def _mock_player_data(player_tag):
    rng = random.Random(sum(ord(character) for character in player_tag))
    wins = rng.randint(100, 2500)
    losses = rng.randint(50, 2000)
    draws = rng.randint(10, 500)
    total = wins + losses + draws
    return {
        "player_name": f"{rng.choice(['RoyalePro', 'ClashMaster', 'TrophyHunter', 'CrownChaser'])}{rng.randint(1, 999)}",
        "trophies": rng.randint(4000, 7500),
        "best_trophies": rng.randint(4500, 8000),
        "level": rng.randint(8, 15),
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "total_battles": total,
        "win_rate": wins / total * 100,
        "clan_name": rng.choice(["Reddit Alpha", "Competitive", "Legend League", "Global Elite"]),
        "clan_tag": f"#CLAN{rng.randint(100, 999)}",
        "is_mock": 1,
    }


def _api_key():
    return (
        current_app.config.get("CLASH_ROYALE_API_KEY")
        or os.environ.get("CLASH_ROYALE_API_KEY")
        or ""
    )


def _mock_mode():
    configured = current_app.config.get("USE_MOCK_DATA")
    if configured is None:
        configured = os.environ.get("USE_MOCK_DATA", "true").lower() == "true"
    elif isinstance(configured, str):
        configured = configured.strip().lower() == "true"
    return bool(configured) or not _api_key()


def _fetch_api_player(player_tag):
    token = _api_key()
    if not token:
        raise RuntimeError("Clash Royale API key is not configured.")
    encoded_tag = quote(player_tag.lstrip("#"), safe="")
    req = urllib.request.Request(
        f"https://api.clashroyale.com/v1/players/%23{encoded_tag}",
        headers={"Accept": "application/json"},
    )
    req.headers["Authorization"] = "Bearer " + token
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(f"Clash Royale API returned HTTP {error.code}.") from None
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        raise RuntimeError("Could not reach the Clash Royale API; try again later.") from None
    if not isinstance(payload, dict):
        raise RuntimeError("Clash Royale API returned an invalid player response.")
    try:
        clan = payload.get("clan") or {}
        wins = int(payload.get("wins", 0))
        losses = int(payload.get("losses", 0))
        draws = int(payload.get("draws", 0))
        battles = int(payload.get("battleCount", wins + losses + draws))
        trophies = int(payload.get("trophies", 0))
        best_trophies = int(payload.get("bestTrophies", 0))
        level = int(payload.get("expLevel", 1))
    except (TypeError, ValueError):
        raise RuntimeError("Clash Royale API returned invalid player statistics.") from None
    return {
        "player_name": str(payload.get("name") or "Unknown")[:100],
        "trophies": trophies,
        "best_trophies": best_trophies,
        "level": level,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "total_battles": battles,
        "win_rate": (wins / battles * 100) if battles else 0,
        "clan_name": str(clan.get("name") or "")[:100],
        "clan_tag": str(clan.get("tag") or "")[:20],
        "is_mock": 0,
    }


def _save_player_stats(database, player_id, values):
    database.execute(
        """
        UPDATE clashroyale_clashroyaleplayer
        SET player_name = ?, trophies = ?, best_trophies = ?, level = ?,
            wins = ?, losses = ?, draws = ?, total_battles = ?, win_rate = ?,
            clan_name = ?, clan_tag = ?, is_mock = ?, last_updated = ?
        WHERE id = ?
        """,
        (
            values["player_name"],
            values["trophies"],
            values["best_trophies"],
            values["level"],
            values["wins"],
            values["losses"],
            values["draws"],
            values["total_battles"],
            values["win_rate"],
            values["clan_name"],
            values["clan_tag"],
            values["is_mock"],
            datetime.now(timezone.utc).isoformat(timespec="seconds"),
            player_id,
        ),
    )


@competitions.get("/clash-royale/")
def clash_royale_leaderboard():
    database = get_db()
    players = database.execute(
        """
        SELECT p.*, u.username
        FROM clashroyale_clashroyaleplayer AS p
        JOIN auth_user AS u ON u.id = p.user_id
        ORDER BY p.trophies DESC, p.id ASC
        LIMIT 100
        """
    ).fetchall()
    total_players = database.execute(
        "SELECT COUNT(*) AS total FROM clashroyale_clashroyaleplayer"
    ).fetchone()["total"]
    user = _current_user()
    user_rank = None
    has_player = False
    if user is not None:
        user_player = database.execute(
            """
            SELECT id, trophies FROM clashroyale_clashroyaleplayer
            WHERE user_id = ? ORDER BY id LIMIT 1
            """,
            (user["id"],),
        ).fetchone()
        has_player = user_player is not None
        if user_player:
            user_rank = database.execute(
                "SELECT COUNT(*) + 1 AS rank FROM clashroyale_clashroyaleplayer WHERE trophies > ?",
                (user_player["trophies"],),
            ).fetchone()["rank"]
    return render_template(
        "competitions/leaderboard.html",
        players=players,
        total_players=total_players,
        top_player=players[0] if players else None,
        user_rank=user_rank,
        has_player=has_player,
        use_mock_data=_mock_mode(),
    )


@competitions.route("/clash-royale/connect/", methods=["GET", "POST"])
@login_required
def connect_account():
    database = get_db()
    user = _current_user()
    existing = database.execute(
        "SELECT id FROM clashroyale_clashroyaleplayer WHERE user_id = ? LIMIT 1",
        (user["id"],),
    ).fetchone()
    if existing:
        flash("You already have a connected Clash Royale account.", "info")
        return redirect(url_for("competitions.clash_royale_leaderboard"))
    if request.method == "GET":
        return render_template("competitions/connect.html", use_mock_data=_mock_mode())

    tag = request.form.get("player_tag", "").strip().upper()
    if not tag.startswith("#"):
        tag = "#" + tag
    if not re.fullmatch(r"#[A-Z0-9]{3,15}", tag):
        flash("Enter a valid player tag (3–15 letters or digits, optionally starting with #).", "error")
        return render_template("competitions/connect.html", use_mock_data=_mock_mode()), 400
    duplicate = database.execute(
        "SELECT id FROM clashroyale_clashroyaleplayer WHERE player_tag = ?",
        (tag,),
    ).fetchone()
    if duplicate:
        flash("That player tag is already connected.", "error")
        return render_template("competitions/connect.html", use_mock_data=_mock_mode()), 409
    try:
        values = _mock_player_data(tag) if _mock_mode() else _fetch_api_player(tag)
    except RuntimeError as error:
        flash(str(error), "error")
        return render_template("competitions/connect.html", use_mock_data=False), 502

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        cursor = database.execute(
            """
            INSERT INTO clashroyale_clashroyaleplayer
                (player_tag, player_name, trophies, best_trophies, level,
                 wins, losses, draws, total_battles, win_rate, clan_name,
                 clan_tag, is_mock, last_updated, created_at, user_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tag,
                values["player_name"],
                values["trophies"],
                values["best_trophies"],
                values["level"],
                values["wins"],
                values["losses"],
                values["draws"],
                values["total_battles"],
                values["win_rate"],
                values["clan_name"],
                values["clan_tag"],
                values["is_mock"],
                now,
                now,
                user["id"],
            ),
        )
        database.commit()
    except sqlite3.IntegrityError:
        database.rollback()
        flash("That player tag or account is already connected.", "error")
        return redirect(url_for("competitions.connect_account"))
    flash(
        f"Connected {values['player_name']} ({'demo' if values['is_mock'] else 'live'} stats).",
        "success",
    )
    return redirect(url_for("competitions.clash_royale_leaderboard"))


@competitions.route("/clash-royale/refresh/", methods=["GET", "POST"])
@login_required
def refresh_stats():
    if request.method == "GET":
        flash("Use the Refresh Stats button to update your account.", "info")
        return redirect(url_for("competitions.clash_royale_leaderboard"))
    user = _current_user()
    database = get_db()
    player = database.execute(
        """
        SELECT * FROM clashroyale_clashroyaleplayer
        WHERE user_id = ? ORDER BY id LIMIT 1
        """,
        (user["id"],),
    ).fetchone()
    if player is None:
        flash("No Clash Royale account is connected to your account.", "error")
        return redirect(url_for("competitions.clash_royale_leaderboard"))
    try:
        if player["is_mock"]:
            values = dict(player)
            rng = random.Random(
                sum(ord(character) for character in player["player_tag"])
                + int(datetime.now(timezone.utc).timestamp())
            )
            values["trophies"] = max(0, player["trophies"] + rng.randint(-50, 100))
            values["best_trophies"] = max(player["best_trophies"], values["trophies"])
            values["wins"] += rng.randint(0, 10)
            values["losses"] += rng.randint(0, 5)
            values["draws"] += rng.randint(0, 2)
            values["total_battles"] = values["wins"] + values["losses"] + values["draws"]
            values["win_rate"] = (
                values["wins"] / values["total_battles"] * 100
                if values["total_battles"]
                else 0
            )
            values["is_mock"] = 1
        else:
            values = _fetch_api_player(player["player_tag"])
        _save_player_stats(database, player["id"], values)
        database.commit()
    except RuntimeError as error:
        database.rollback()
        flash(f"Stats refresh failed: {error}", "error")
        return redirect(url_for("competitions.clash_royale_leaderboard"))
    flash(
        "Mock stats refreshed." if values["is_mock"] else "Stats refreshed from the Clash Royale API.",
        "success",
    )
    return redirect(url_for("competitions.clash_royale_leaderboard"))


@competitions.get("/clash-royale/about/")
def about_clash_royale():
    total_players = get_db().execute(
        "SELECT COUNT(*) AS total FROM clashroyale_clashroyaleplayer"
    ).fetchone()["total"]
    return render_template(
        "competitions/about.html",
        total_players=total_players,
        use_mock_data=_mock_mode(),
    )


@competitions.route("/clash-royale/toggle-data-source/", methods=["GET", "POST"])
@login_required
def toggle_data_source():
    if request.method == "GET":
        flash("Use the data-source button to change your account mode.", "info")
        return redirect(url_for("competitions.clash_royale_leaderboard"))
    user = _current_user()
    database = get_db()
    player = database.execute(
        """
        SELECT id, is_mock FROM clashroyale_clashroyaleplayer
        WHERE user_id = ? ORDER BY id LIMIT 1
        """,
        (user["id"],),
    ).fetchone()
    if player is None:
        flash("No Clash Royale account is connected.", "error")
    elif player["is_mock"]:
        if not _api_key():
            flash("API key is not configured; this account must remain in demo mode.", "error")
        else:
            database.execute(
                "UPDATE clashroyale_clashroyaleplayer SET is_mock = 0 WHERE id = ? AND user_id = ?",
                (player["id"], user["id"]),
            )
            database.commit()
            flash("Switched to live API data. Refresh to fetch current stats.", "success")
    else:
        database.execute(
            "UPDATE clashroyale_clashroyaleplayer SET is_mock = 1 WHERE id = ? AND user_id = ?",
            (player["id"], user["id"]),
        )
        database.commit()
        flash("Switched to demo data. Refresh to update mock stats.", "success")
    return redirect(url_for("competitions.clash_royale_leaderboard"))
