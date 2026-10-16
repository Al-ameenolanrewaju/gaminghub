import json
import secrets
import sqlite3
import time
from pathlib import Path

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from . import csrf_token, get_db


live_games = Blueprint("live_games", __name__)
GAME_DEFINITIONS = {
    "HUB_NEON_SPRINT": {
        "title": "Neon Sprint",
        "description": "Race your friends by boosting your runner to the finish.",
        "goal": 25,
        "duration": 90,
        "action": "boost",
    },
    "HUB_CIPHER_CLASH": {
        "title": "Cipher Clash",
        "description": "Crack a hidden four-digit code with no repeated digits.",
        "goal": 1,
        "duration": 90,
        "action": "guess",
    },
    "HUB_TACTIC_GRID": {
        "title": "Tactic Grid",
        "description": "Outmaneuver your opponent in a timed Connect Four duel.",
        "goal": 1,
        "duration": 180,
        "action": "column",
    },
    "HUB_REACTION_RELAY": {
        "title": "Reaction Relay",
        "description": "Wait for the green signal, then react first. False starts cost points.",
        "goal": 5,
        "duration": 90,
        "action": "react",
    },
}
GAME_SLUGS = {
    game_type.removeprefix("HUB_").lower().replace("_", "-"): game_type
    for game_type in GAME_DEFINITIONS
}


def initialize_live_games(database_path):
    path = Path(database_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    database = sqlite3.connect(path, timeout=10)
    try:
        database.executescript(
            """
            CREATE TABLE IF NOT EXISTS live_game_round (
                room_code TEXT PRIMARY KEY,
                game_type TEXT NOT NULL,
                status TEXT NOT NULL,
                started_at REAL NOT NULL,
                ends_at REAL NOT NULL,
                challenge TEXT
            );
            CREATE TABLE IF NOT EXISTS live_game_player (
                room_code TEXT NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                score INTEGER NOT NULL DEFAULT 0,
                last_action_at REAL NOT NULL DEFAULT 0,
                PRIMARY KEY (room_code, user_id)
            );
            CREATE TABLE IF NOT EXISTS live_game_result (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                room_code TEXT NOT NULL,
                game_type TEXT NOT NULL,
                started_at REAL NOT NULL,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                score INTEGER NOT NULL,
                won INTEGER NOT NULL DEFAULT 0,
                UNIQUE (room_code, started_at, user_id)
            );
            """
        )
    finally:
        database.close()


def _runtime_db():
    database = sqlite3.connect(
        current_app.config["GAME_DATABASE"], timeout=10, isolation_level=None
    )
    database.row_factory = sqlite3.Row
    return database


def _current_user():
    user_id = session.get("user_id")
    if user_id is None:
        return None
    return get_db().execute(
        "SELECT id, username FROM auth_user WHERE id = ? AND is_active = 1",
        (user_id,),
    ).fetchone()


def _room_and_players(room_code):
    database = get_db()
    room = database.execute(
        """
        SELECT room.*, host.username AS host_username
        FROM core_room AS room
        JOIN auth_user AS host ON host.id = room.host_id
        WHERE room.room_code = ? AND room.is_active = 1
        """,
        (room_code,),
    ).fetchone()
    if room is None:
        abort(404)
    if room["game"] not in GAME_DEFINITIONS:
        abort(404)
    players = database.execute(
        """
        SELECT id, username FROM auth_user WHERE id = ?
        UNION ALL
        SELECT user.id, user.username
        FROM core_room_players AS players
        JOIN auth_user AS user ON user.id = players.user_id
        WHERE players.room_id = ?
        ORDER BY username
        """,
        (room["host_id"], room["id"]),
    ).fetchall()
    return room, players


def _require_room_player(room_code):
    user = _current_user()
    if user is None:
        abort(401)
    room, players = _room_and_players(room_code)
    if user["id"] not in {player["id"] for player in players}:
        abort(403)
    return user, room, players


def _new_challenge(game_type, players, now):
    if game_type == "HUB_CIPHER_CLASH":
        return {
            "secret": "".join(str(digit) for digit in secrets.SystemRandom().sample(range(10), 4)),
            "feedback": {},
        }
    if game_type == "HUB_TACTIC_GRID":
        return {
            "board": [[None for _ in range(7)] for _ in range(6)],
            "current_turn": players[0]["id"],
            "first_player": players[0]["id"],
            "winner": None,
        }
    if game_type == "HUB_REACTION_RELAY":
        return {
            "round": 1,
            "signal_at": now + 2 + secrets.randbelow(3000) / 1000,
            "winner": None,
            "false_starts": {},
        }
    return None


def _connect_four_winner(board, row, column, marker):
    for row_step, column_step in ((0, 1), (1, 0), (1, 1), (1, -1)):
        count = 1
        for direction in (-1, 1):
            next_row = row + row_step * direction
            next_column = column + column_step * direction
            while (
                0 <= next_row < 6
                and 0 <= next_column < 7
                and board[next_row][next_column] == marker
            ):
                count += 1
                next_row += row_step * direction
                next_column += column_step * direction
        if count >= 4:
            return True
    return False


def _record_result(database, game_round, scores, challenge):
    winner_id = challenge.get("winner") if challenge else None
    if winner_id is None and scores:
        highest_score = max(player["score"] for player in scores)
        leaders = [player for player in scores if player["score"] == highest_score]
        if highest_score > 0 and len(leaders) == 1:
            winner_id = leaders[0]["user_id"]
    database.executemany(
        """
        INSERT OR IGNORE INTO live_game_result
            (room_code, game_type, started_at, user_id, username, score, won)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        [
            (
                game_round["room_code"],
                game_round["game_type"],
                game_round["started_at"],
                player["user_id"],
                player["username"],
                player["score"],
                int(player["user_id"] == winner_id),
            )
            for player in scores
        ],
    )


def _round_state(room_code, user_id, room, players):
    now = time.time()
    database = _runtime_db()
    try:
        database.execute("BEGIN IMMEDIATE")
        game_round = database.execute(
            "SELECT * FROM live_game_round WHERE room_code = ?", (room_code,)
        ).fetchone()
        if game_round is None:
            database.commit()
            return {
                "status": "waiting",
                "players": [dict(player, score=0) for player in players],
                "game": GAME_DEFINITIONS[room["game"]],
            }
        scores = database.execute(
            """
            SELECT user_id, username, score
            FROM live_game_player WHERE room_code = ?
            ORDER BY score DESC, username
            """,
            (room_code,),
        ).fetchall()
        if game_round["status"] == "playing" and now >= game_round["ends_at"]:
            challenge_data = (
                json.loads(game_round["challenge"]) if game_round["challenge"] else None
            )
            _record_result(database, game_round, scores, challenge_data)
            database.execute(
                "UPDATE live_game_round SET status = 'finished' WHERE room_code = ?",
                (room_code,),
            )
            game_round = database.execute(
                "SELECT * FROM live_game_round WHERE room_code = ?", (room_code,)
            ).fetchone()
        if not any(player["user_id"] == user_id for player in scores):
            database.rollback()
            abort(403, description="You joined after this game started.")
        challenge = json.loads(game_round["challenge"]) if game_round["challenge"] else None
        if game_round["game_type"] == "HUB_CIPHER_CLASH":
            user_feedback = (challenge.get("feedback") or {}).get(str(user_id), [])
            public_challenge = {
                "attempts": user_feedback,
                "solved": bool(user_feedback and user_feedback[-1]["exact"] == 4),
                "max_attempts": 10,
            }
            if game_round["status"] == "finished":
                public_challenge["answer"] = challenge["secret"]
        elif game_round["game_type"] == "HUB_TACTIC_GRID":
            public_challenge = challenge
            public_challenge["your_marker"] = (
                "X" if user_id == challenge["first_player"] else "O"
            )
            public_challenge["your_turn"] = challenge["current_turn"] == user_id
        elif game_round["game_type"] == "HUB_REACTION_RELAY":
            public_challenge = {
                "round": challenge["round"],
                "signal": now >= challenge["signal_at"],
                "false_start": str(user_id) in challenge["false_starts"],
                "last_winner": next(
                    (
                        player["username"]
                        for player in scores
                        if player["user_id"] == challenge["winner"]
                    ),
                    None,
                ),
            }
        else:
            public_challenge = None
        database.commit()
        return {
            "status": game_round["status"],
            "players": [dict(player) for player in scores],
            "challenge": public_challenge,
            "time_left": max(0, int(game_round["ends_at"] - now + 0.999)),
            "game": GAME_DEFINITIONS[game_round["game_type"]],
        }
    finally:
        database.close()


@live_games.get("/originals/")
def originals():
    return render_template("rooms/originals.html", games=GAME_DEFINITIONS)


@live_games.get("/originals/leaderboard/")
@live_games.get("/originals/<string:game_slug>/leaderboard/")
def leaderboard(game_slug=None):
    game_type = GAME_SLUGS.get(game_slug) if game_slug else None
    if game_slug and game_type is None:
        abort(404)
    database = _runtime_db()
    try:
        query = """
            SELECT user_id, MAX(username) AS username, COUNT(*) AS matches,
                   SUM(won) AS wins, SUM(score) AS points
            FROM live_game_result
        """
        parameters = ()
        if game_type:
            query += " WHERE game_type = ?"
            parameters = (game_type,)
        query += """
            GROUP BY user_id
            ORDER BY wins DESC, points DESC, matches DESC, username COLLATE NOCASE
            LIMIT 100
        """
        players = database.execute(query, parameters).fetchall()
    finally:
        database.close()
    return render_template(
        "rooms/leaderboard.html",
        players=players,
        games=GAME_DEFINITIONS,
        selected_game=game_type,
        selected_slug=game_slug,
    )


@live_games.get("/rooms/<string:room_code>/play/")
def play_room(room_code):
    user, room, players = _require_room_player(room_code)
    state = _round_state(room_code, user["id"], room, players)
    return render_template(
        "rooms/live_game.html",
        room=room,
        players=players,
        is_host=user["id"] == room["host_id"],
        state=state,
        csrf=csrf_token(),
    )


@live_games.post("/rooms/<string:room_code>/play/start/")
def start_room_game(room_code):
    user, room, players = _require_room_player(room_code)
    if user["id"] != room["host_id"]:
        abort(403)
    if len(players) < 2:
        flash("Invite at least one other player before starting.", "warning")
        return redirect(url_for("live_games.play_room", room_code=room_code))
    if room["game"] == "HUB_TACTIC_GRID" and len(players) != 2:
        flash("Tactic Grid is a two-player game; remove extra players first.", "warning")
        return redirect(url_for("live_games.play_room", room_code=room_code))

    now = time.time()
    game = GAME_DEFINITIONS[room["game"]]
    challenge = _new_challenge(room["game"], players, now)
    challenge = json.dumps(challenge) if challenge is not None else None
    database = _runtime_db()
    try:
        database.execute("BEGIN IMMEDIATE")
        current_round = database.execute(
            "SELECT * FROM live_game_round WHERE room_code = ?",
            (room_code,),
        ).fetchone()
        if current_round and current_round["status"] == "playing" and now < current_round["ends_at"]:
            database.rollback()
            flash("This game is already in progress.", "info")
            return redirect(url_for("live_games.play_room", room_code=room_code))
        if current_round and current_round["status"] == "playing":
            previous_scores = database.execute(
                """
                SELECT user_id, username, score
                FROM live_game_player WHERE room_code = ?
                """,
                (room_code,),
            ).fetchall()
            previous_challenge = (
                json.loads(current_round["challenge"])
                if current_round["challenge"]
                else None
            )
            _record_result(database, current_round, previous_scores, previous_challenge)
        database.execute("DELETE FROM live_game_player WHERE room_code = ?", (room_code,))
        database.executemany(
            """
            INSERT INTO live_game_player (room_code, user_id, username)
            VALUES (?, ?, ?)
            """,
            [(room_code, player["id"], player["username"]) for player in players],
        )
        database.execute(
            """
            INSERT INTO live_game_round
                (room_code, game_type, status, started_at, ends_at, challenge)
            VALUES (?, ?, 'playing', ?, ?, ?)
            ON CONFLICT(room_code) DO UPDATE SET
                game_type = excluded.game_type,
                status = 'playing',
                started_at = excluded.started_at,
                ends_at = excluded.ends_at,
                challenge = excluded.challenge
            """,
            (room_code, room["game"], now, now + game["duration"], challenge),
        )
        database.commit()
    except Exception:
        if database.in_transaction:
            database.rollback()
        raise
    finally:
        database.close()
    return redirect(url_for("live_games.play_room", room_code=room_code))


@live_games.get("/api/rooms/<string:room_code>/game/")
def game_state(room_code):
    user, room, players = _require_room_player(room_code)
    response = jsonify(_round_state(room_code, user["id"], room, players))
    response.headers["Cache-Control"] = "no-store"
    return response


@live_games.post("/api/rooms/<string:room_code>/game/action/")
def game_action(room_code):
    user, room, _ = _require_room_player(room_code)
    game = GAME_DEFINITIONS[room["game"]]
    now = time.time()
    database = _runtime_db()
    try:
        database.execute("BEGIN IMMEDIATE")
        game_round = database.execute(
            "SELECT * FROM live_game_round WHERE room_code = ?", (room_code,)
        ).fetchone()
        player = database.execute(
            """
            SELECT score, last_action_at
            FROM live_game_player WHERE room_code = ? AND user_id = ?
            """,
            (room_code, user["id"]),
        ).fetchone()
        if game_round is None or game_round["status"] != "playing" or now >= game_round["ends_at"]:
            if game_round and game_round["status"] == "playing":
                scores = database.execute(
                    """
                    SELECT user_id, username, score
                    FROM live_game_player WHERE room_code = ?
                    """,
                    (room_code,),
                ).fetchall()
                challenge_data = (
                    json.loads(game_round["challenge"])
                    if game_round["challenge"]
                    else None
                )
                _record_result(database, game_round, scores, challenge_data)
                database.execute(
                    "UPDATE live_game_round SET status = 'finished' WHERE room_code = ?",
                    (room_code,),
                )
                database.commit()
                return jsonify({"status": "finished"})
            database.rollback()
            abort(409, description="The game is not running.")
        if player is None:
            database.rollback()
            abort(403, description="You joined after this game started.")
        if game["action"] in {"boost", "react"} and now - player["last_action_at"] < 0.08:
            database.rollback()
            abort(429, description="Slow down and try again.")

        score_delta = 0
        status = "playing"
        challenge = json.loads(game_round["challenge"]) if game_round["challenge"] else None
        response_data = {"status": "playing", "accepted": True}
        if game["action"] == "boost":
            score_delta = 1
        elif game["action"] == "guess":
            try:
                guess = request.form.get("guess", "")
                if (
                    len(guess) != 4
                    or not guess.isascii()
                    or not guess.isdigit()
                    or len(set(guess)) != 4
                ):
                    raise ValueError
            except (TypeError, ValueError):
                database.rollback()
                abort(400, description="Enter exactly four different digits (0-9).")
            feedback_by_player = challenge.setdefault("feedback", {})
            attempts = feedback_by_player.setdefault(str(user["id"]), [])
            if len(attempts) >= 10:
                database.rollback()
                abort(409, description="You have used all ten attempts.")
            secret = challenge["secret"]
            exact = sum(left == right for left, right in zip(guess, secret))
            misplaced = sum(min(guess.count(digit), secret.count(digit)) for digit in set(guess)) - exact
            attempts.append({"guess": guess, "exact": exact, "misplaced": misplaced})
            if exact == 4:
                score_delta = 1
                status = "finished"
                challenge["winner"] = user["id"]
                response_data["solved"] = True
            else:
                response_data["solved"] = False
                response_data["exact"] = exact
                response_data["misplaced"] = misplaced
                participants = database.execute(
                    "SELECT user_id FROM live_game_player WHERE room_code = ?",
                    (room_code,),
                ).fetchall()
                if all(
                    len(feedback_by_player.get(str(participant["user_id"]), [])) >= 10
                    for participant in participants
                ):
                    status = "finished"
        elif game["action"] == "column":
            try:
                column = int(request.form.get("column", ""))
            except ValueError:
                database.rollback()
                abort(400, description="Choose a board column.")
            if not 0 <= column < 7:
                database.rollback()
                abort(400, description="Choose a column from 1 to 7.")
            if challenge["current_turn"] != user["id"]:
                database.rollback()
                abort(409, description="Wait for your turn.")
            board = challenge["board"]
            row = next((index for index in range(5, -1, -1) if board[index][column] is None), None)
            if row is None:
                database.rollback()
                abort(409, description="That column is full.")
            marker = "X" if user["id"] == challenge["first_player"] else "O"
            board[row][column] = marker
            if _connect_four_winner(board, row, column, marker):
                challenge["winner"] = user["id"]
                score_delta = 1
                status = "finished"
                response_data["winner"] = True
            elif all(cell is not None for board_row in board for cell in board_row):
                status = "finished"
                response_data["draw"] = True
            else:
                player_ids = [int(item["user_id"]) for item in database.execute(
                    "SELECT user_id FROM live_game_player WHERE room_code = ? ORDER BY user_id",
                    (room_code,),
                ).fetchall()]
                challenge["current_turn"] = next(
                    player_id for player_id in player_ids if player_id != user["id"]
                )
        elif game["action"] == "react":
            false_starts = challenge.setdefault("false_starts", {})
            if now < challenge["signal_at"]:
                current_score = player["score"]
                database.execute(
                    """
                    UPDATE live_game_player SET score = ?, last_action_at = ?
                    WHERE room_code = ? AND user_id = ?
                    """,
                    (max(0, current_score - 1), now, room_code, user["id"]),
                )
                false_starts[str(user["id"])] = challenge["round"]
                response_data.update(accepted=False, false_start=True)
                database.execute(
                    "UPDATE live_game_round SET challenge = ? WHERE room_code = ?",
                    (json.dumps(challenge), room_code),
                )
                database.commit()
                return jsonify(response_data)
            score_delta = 1
            challenge["winner"] = user["id"]
            challenge["round"] += 1
            challenge["false_starts"] = {}
            if player["score"] + 1 >= game["goal"]:
                status = "finished"
            else:
                challenge["signal_at"] = now + 1.5 + secrets.randbelow(3000) / 1000
            response_data["round_winner"] = user["username"]

        database.execute(
            """
            UPDATE live_game_player SET score = score + ?, last_action_at = ?
            WHERE room_code = ? AND user_id = ?
            """,
            (score_delta, now, room_code, user["id"]),
        )
        top_score = database.execute(
            "SELECT MAX(score) FROM live_game_player WHERE room_code = ?",
            (room_code,),
        ).fetchone()[0]
        if top_score >= game["goal"]:
            status = "finished"
        database.execute(
            "UPDATE live_game_round SET challenge = ?, status = ? WHERE room_code = ?",
            (json.dumps(challenge) if challenge is not None else None, status, room_code),
        )
        if status == "finished":
            result_round = dict(game_round)
            result_round["challenge"] = (
                json.dumps(challenge) if challenge is not None else None
            )
            final_scores = database.execute(
                """
                SELECT user_id, username, score
                FROM live_game_player WHERE room_code = ?
                ORDER BY score DESC, username
                """,
                (room_code,),
            ).fetchall()
            _record_result(database, result_round, final_scores, challenge)
        database.commit()
        response_data["status"] = status
        return jsonify(response_data)
    except Exception:
        if database.in_transaction:
            database.rollback()
        raise
    finally:
        database.close()
