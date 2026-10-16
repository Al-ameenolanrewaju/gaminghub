from functools import wraps
import json

from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for

from . import get_db


admin = Blueprint("admin", __name__, url_prefix="/admin")


def staff_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        user_id = session.get("user_id")
        if user_id is None:
            return redirect(url_for("auth_rooms.login", next=request.path))
        user = get_db().execute(
            "SELECT is_active, is_staff, is_superuser FROM auth_user WHERE id = ?",
            (user_id,),
        ).fetchone()
        if user is None or not user["is_active"] or not (
            user["is_staff"] or user["is_superuser"]
        ):
            abort(403)
        return view(*args, **kwargs)

    return wrapped


@admin.get("/")
@staff_required
def dashboard():
    database = get_db()
    search = request.args.get("q", "").strip()[:100]
    user_query = """
        SELECT id, username, email, is_active, is_staff, is_superuser, date_joined
        FROM auth_user
    """
    user_parameters = ()
    if search:
        user_query += " WHERE username LIKE ? OR email LIKE ?"
        pattern = f"%{search}%"
        user_parameters = (pattern, pattern)
    user_query += " ORDER BY date_joined DESC, id DESC LIMIT 100"
    users = database.execute(user_query, user_parameters).fetchall()
    rooms = database.execute(
        """
        SELECT room.id, room.title, room.game, room.room_code, room.is_active,
               room.max_players, room.created_at, host.username AS host_username,
               (SELECT COUNT(*) FROM core_room_players AS members
                WHERE members.room_id = room.id) + 1 AS current_players
        FROM core_room AS room
        JOIN auth_user AS host ON host.id = room.host_id
        ORDER BY room.created_at DESC LIMIT 100
        """
    ).fetchall()
    totals = {
        "users": database.execute(
            "SELECT COUNT(*) FROM auth_user"
        ).fetchone()[0],
        "active_rooms": database.execute(
            "SELECT COUNT(*) FROM core_room WHERE is_active = 1"
        ).fetchone()[0],
        "pending_submissions": database.execute(
            "SELECT COUNT(*) FROM core_statsubmission WHERE status = 'pending'"
        ).fetchone()[0],
        "pending_payments": database.execute(
            "SELECT COUNT(*) FROM tournament_tournamentsubscription "
            "WHERE payment_status = 'pending'"
        ).fetchone()[0],
    }
    submissions = database.execute(
        """
        SELECT submission.id, submission.game_type, submission.status,
               submission.total_score, submission.created_at, user.username
        FROM core_statsubmission AS submission
        JOIN auth_user AS user ON user.id = submission.user_id
        ORDER BY submission.created_at DESC LIMIT 100
        """
    ).fetchall()
    payments = database.execute(
        """
        SELECT payment.id, payment.payment_status, payment.payment_amount,
               payment.payment_method, payment.subscription_date,
               payment.payment_proof,
               tournament.title AS tournament_title, user.username
        FROM tournament_tournamentsubscription AS payment
        JOIN tournament_tournament AS tournament ON tournament.id = payment.tournament_id
        JOIN auth_user AS user ON user.id = payment.user_id
        ORDER BY payment.subscription_date DESC LIMIT 100
        """
    ).fetchall()
    tournaments = database.execute(
        """
        SELECT tournament.id, tournament.title, tournament.status,
               tournament.current_participants, tournament.max_participants,
               game.name AS game_name, result.first_place_id,
               result.second_place_id, result.third_place_id
        FROM tournament_tournament AS tournament
        LEFT JOIN tournament_game AS game ON game.id = tournament.game_id
        LEFT JOIN tournament_tournamentresult AS result
          ON result.tournament_id = tournament.id
        ORDER BY tournament.start_date DESC LIMIT 100
        """
    ).fetchall()
    tournament_players = {}
    for tournament in tournaments:
        tournament_players[tournament["id"]] = database.execute(
            """
            SELECT DISTINCT user.id, user.username
            FROM tournament_tournamentsubscription AS subscription
            JOIN auth_user AS user ON user.id = subscription.user_id
            WHERE subscription.tournament_id = ?
              AND subscription.payment_status = 'completed'
            ORDER BY user.username
            """,
            (tournament["id"],),
        ).fetchall()
    matches = database.execute(
        """
        SELECT match.id, match.tournament_id, match.round_number,
               match.match_number, match.status, match.score_player1,
               match.score_player2, match.player1_id, match.player2_id,
               match.winner_id, tournament.title AS tournament_title,
               player1.username AS player1_username,
               player2.username AS player2_username
        FROM tournament_match AS match
        JOIN tournament_tournament AS tournament ON tournament.id = match.tournament_id
        LEFT JOIN auth_user AS player1 ON player1.id = match.player1_id
        LEFT JOIN auth_user AS player2 ON player2.id = match.player2_id
        ORDER BY tournament.start_date DESC, match.round_number, match.match_number
        LIMIT 200
        """
    ).fetchall()
    games = database.execute(
        "SELECT id, name, is_active FROM tournament_game ORDER BY name"
    ).fetchall()
    return render_template(
        "admin/dashboard.html",
        submissions=submissions,
        payments=payments,
        tournaments=tournaments,
        tournament_players=tournament_players,
        matches=matches,
        games=games,
        users=users,
        rooms=rooms,
        totals=totals,
        search=search,
    )


@admin.post("/users/<int:user_id>/")
@staff_required
def update_user(user_id):
    action = request.form.get("action")
    if action not in {"activate", "deactivate", "grant_staff", "revoke_staff"}:
        abort(400, description="Unsupported user-management action.")

    actor_id = session["user_id"]
    database = get_db()
    target = database.execute(
        """
        SELECT id, is_active, is_staff, is_superuser
        FROM auth_user WHERE id = ?
        """,
        (user_id,),
    ).fetchone()
    if target is None:
        abort(404)
    if user_id == actor_id:
        abort(400, description="You cannot change your own account status or role.")
    if target["is_superuser"]:
        abort(400, description="Superuser accounts cannot be changed here.")
    if action in {"grant_staff", "revoke_staff"}:
        actor = database.execute(
            "SELECT is_superuser FROM auth_user WHERE id = ?", (actor_id,)
        ).fetchone()
        if actor is None or not actor["is_superuser"]:
            abort(403, description="Only a superuser can change staff roles.")

    database.execute("BEGIN IMMEDIATE")
    if action == "deactivate" and target["is_active"] and target["is_staff"]:
        active_staff = database.execute(
            """
            SELECT COUNT(*) FROM auth_user
            WHERE is_active = 1 AND (is_staff = 1 OR is_superuser = 1)
            """
        ).fetchone()[0]
        if active_staff <= 1:
            database.rollback()
            abort(400, description="The last active staff account cannot be deactivated.")
    if action == "revoke_staff" and target["is_staff"] and target["is_active"]:
        active_staff = database.execute(
            """
            SELECT COUNT(*) FROM auth_user
            WHERE is_active = 1 AND (is_staff = 1 OR is_superuser = 1)
            """
        ).fetchone()[0]
        if active_staff <= 1:
            database.rollback()
            abort(400, description="The last active staff role cannot be removed.")

    if action in {"activate", "deactivate"}:
        database.execute(
            "UPDATE auth_user SET is_active = ? WHERE id = ?",
            (int(action == "activate"), user_id),
        )
        message = "User account activated." if action == "activate" else "User account deactivated."
    else:
        database.execute(
            "UPDATE auth_user SET is_staff = ? WHERE id = ?",
            (int(action == "grant_staff"), user_id),
        )
        message = "Staff access granted." if action == "grant_staff" else "Staff access removed."
    database.commit()
    flash(message, "success")
    return redirect(url_for("admin.dashboard", q=request.form.get("q", "")))


@admin.post("/rooms/<int:room_id>/status/")
@staff_required
def update_room_status(room_id):
    is_active = request.form.get("is_active")
    if is_active not in {"0", "1"}:
        abort(400, description="Invalid room availability.")
    cursor = get_db().execute(
        "UPDATE core_room SET is_active = ? WHERE id = ?",
        (int(is_active), room_id),
    )
    if cursor.rowcount == 0:
        abort(404)
    get_db().commit()
    flash("Room availability updated.", "success")
    return redirect(url_for("admin.dashboard"))


@admin.post("/submissions/<int:submission_id>/status/")
@staff_required
def update_submission(submission_id):
    status = request.form.get("status")
    if status not in {"pending", "verified", "rejected"}:
        abort(400, description="Unsupported submission status.")

    database = get_db()
    exists = database.execute(
        "SELECT id FROM core_statsubmission WHERE id = ?", (submission_id,)
    ).fetchone()
    if exists is None:
        abort(404)
    verified = int(status == "verified")
    verified_by = session["user_id"] if verified else None
    verified_at = "CURRENT_TIMESTAMP" if verified else "NULL"
    if verified:
        database.execute(
            f"""
            UPDATE core_statsubmission
            SET status = ?, verified = 1, verified_by_id = ?,
                verified_at = {verified_at}, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (status, verified_by, submission_id),
        )
    else:
        database.execute(
            """
            UPDATE core_statsubmission
            SET status = ?, verified = ?, verified_by_id = NULL,
                verified_at = NULL, rejection_reason = ?, updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (
                status,
                verified,
                request.form.get("rejection_reason", "").strip() if status == "rejected" else "",
                submission_id,
            ),
        )
    database.commit()
    flash("Submission status updated.", "success")
    return redirect(url_for("admin.dashboard"))


@admin.post("/payments/<int:subscription_id>/status/")
@staff_required
def update_payment(subscription_id):
    status = request.form.get("status")
    allowed_statuses = {"pending", "processing", "completed", "failed", "refunded"}
    if status not in allowed_statuses:
        abort(400, description="Unsupported payment status.")

    database = get_db()
    database.execute("BEGIN IMMEDIATE")
    subscription = database.execute(
        """
        SELECT tournament_id, payment_status FROM tournament_tournamentsubscription
        WHERE id = ?
        """,
        (subscription_id,),
    ).fetchone()
    if subscription is None:
        database.rollback()
        abort(404)

    tournament = database.execute(
        """
        SELECT current_participants, max_participants
        FROM tournament_tournament WHERE id = ?
        """,
        (subscription["tournament_id"],),
    ).fetchone()
    was_completed = subscription["payment_status"] == "completed"
    now_completed = status == "completed"
    if now_completed and not was_completed:
        if tournament is None or tournament["current_participants"] >= tournament["max_participants"]:
            database.rollback()
            flash("Payment cannot be confirmed: tournament is full or unavailable.", "error")
            return redirect(url_for("admin.dashboard"))
        database.execute(
            """
            UPDATE tournament_tournament
            SET current_participants = current_participants + 1,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (subscription["tournament_id"],),
        )
    elif was_completed and not now_completed and tournament is not None:
        database.execute(
            """
            UPDATE tournament_tournament
            SET current_participants = MAX(current_participants - 1, 0),
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
            """,
            (subscription["tournament_id"],),
        )

    verified_at = "CURRENT_TIMESTAMP" if now_completed else "NULL"
    database.execute(
        f"""
        UPDATE tournament_tournamentsubscription
        SET payment_status = ?, verified_by_id = ?, verified_at = {verified_at},
            admin_notes = ?
        WHERE id = ?
        """,
        (
            status,
            session["user_id"] if now_completed else None,
            request.form.get("admin_notes", "").strip(),
            subscription_id,
        ),
    )
    database.commit()
    flash("Payment status updated.", "success")
    return redirect(url_for("admin.dashboard"))


@admin.post("/tournaments/<int:tournament_id>/status/")
@staff_required
def update_tournament(tournament_id):
    status = request.form.get("status")
    if status not in {"upcoming", "ongoing", "completed", "cancelled"}:
        abort(400, description="Unsupported tournament status.")
    cursor = get_db().execute(
        """
        UPDATE tournament_tournament
        SET status = ?, updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (status, tournament_id),
    )
    if cursor.rowcount == 0:
        abort(404)
    get_db().commit()
    flash("Tournament status updated.", "success")
    return redirect(url_for("admin.dashboard"))


@admin.post("/games/<int:game_id>/active/")
@staff_required
def update_game_active(game_id):
    is_active = request.form.get("is_active")
    if is_active not in {"0", "1"}:
        abort(400, description="Invalid game availability.")
    cursor = get_db().execute(
        "UPDATE tournament_game SET is_active = ? WHERE id = ?",
        (int(is_active), game_id),
    )
    if cursor.rowcount == 0:
        abort(404)
    get_db().commit()
    flash("Game availability updated.", "success")
    return redirect(url_for("admin.dashboard"))


@admin.post("/matches/<int:match_id>/")
@staff_required
def update_match(match_id):
    database = get_db()
    match = database.execute(
        """
        SELECT id, player1_id, player2_id
        FROM tournament_match WHERE id = ?
        """,
        (match_id,),
    ).fetchone()
    if match is None:
        abort(404)

    status = request.form.get("status")
    if status not in {"scheduled", "ongoing", "completed", "cancelled"}:
        abort(400, description="Unsupported match status.")
    try:
        score_player1 = int(request.form.get("score_player1", "0"))
        score_player2 = int(request.form.get("score_player2", "0"))
    except ValueError:
        abort(400, description="Match scores must be whole numbers.")
    if not 0 <= score_player1 <= 10000 or not 0 <= score_player2 <= 10000:
        abort(400, description="Match scores must be between 0 and 10000.")

    winner_value = request.form.get("winner_id", "")
    if winner_value:
        try:
            winner_id = int(winner_value)
        except ValueError:
            abort(400, description="Invalid match winner.")
        if winner_id not in (match["player1_id"], match["player2_id"]):
            abort(400, description="The winner must be a player in this match.")
    else:
        winner_id = None

    database.execute(
        """
        UPDATE tournament_match
        SET status = ?, score_player1 = ?, score_player2 = ?, winner_id = ?
        WHERE id = ?
        """,
        (status, score_player1, score_player2, winner_id, match_id),
    )
    database.commit()
    flash("Match result updated.", "success")
    return redirect(url_for("admin.dashboard"))


@admin.post("/tournaments/<int:tournament_id>/results/")
@staff_required
def update_tournament_result(tournament_id):
    database = get_db()
    tournament = database.execute(
        "SELECT status FROM tournament_tournament WHERE id = ?",
        (tournament_id,),
    ).fetchone()
    if tournament is None:
        abort(404)
    if tournament["status"] != "completed":
        abort(400, description="Complete the tournament before publishing final results.")

    winners = []
    for field in ("first_place_id", "second_place_id", "third_place_id"):
        raw_value = request.form.get(field, "").strip()
        try:
            winners.append(int(raw_value) if raw_value else None)
        except ValueError:
            abort(400, description="Choose valid tournament winners.")
    selected = [winner for winner in winners if winner is not None]
    if len(selected) != len(set(selected)):
        abort(400, description="A player can only occupy one podium position.")

    registered_ids = {
        row["user_id"]
        for row in database.execute(
            """
            SELECT user_id FROM tournament_tournamentsubscription
            WHERE tournament_id = ? AND payment_status = 'completed'
            """,
            (tournament_id,),
        ).fetchall()
    }
    if any(winner not in registered_ids for winner in selected):
        abort(400, description="Winners must have a confirmed tournament registration.")
    standings = [
        {"position": position, "user_id": user_id}
        for position, user_id in enumerate(winners, start=1)
        if user_id is not None
    ]
    standings_json = json.dumps(standings)
    existing = database.execute(
        "SELECT id FROM tournament_tournamentresult WHERE tournament_id = ?",
        (tournament_id,),
    ).fetchone()
    values = (
        standings_json,
        winners[0],
        winners[1],
        winners[2],
        tournament_id,
    )
    if existing:
        database.execute(
            """
            UPDATE tournament_tournamentresult
            SET final_standings = ?, first_place_id = ?, second_place_id = ?,
                third_place_id = ?, completed_at = CURRENT_TIMESTAMP
            WHERE tournament_id = ?
            """,
            values,
        )
    else:
        database.execute(
            """
            INSERT INTO tournament_tournamentresult
                (final_standings, completed_at, notes, first_place_id,
                 second_place_id, third_place_id, tournament_id)
            VALUES (?, CURRENT_TIMESTAMP, '', ?, ?, ?, ?)
            """,
            values,
        )
    database.commit()
    flash("Tournament results published.", "success")
    return redirect(url_for("admin.dashboard"))
