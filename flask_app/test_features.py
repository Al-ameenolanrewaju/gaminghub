import io
import base64
import hashlib
import json
import shutil
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from PIL import Image
from werkzeug.security import check_password_hash, generate_password_hash

from flask_app import PROJECT_ROOT, create_app
from flask_app.feature_auth import (
    _password_reset_token,
    _reset_uid,
    _verify_password,
)


class FlaskFeatureTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.sqlite3"
        shutil.copyfile(PROJECT_ROOT / "db.sqlite3", self.database_path)
        self.user_ids = self._create_users()
        self.tournament_id = self._create_tournament()
        self.app = create_app(
            {
                "DATABASE": str(self.database_path),
                "GAME_DATABASE": str(Path(self.temp_dir.name) / "live_games.sqlite3"),
                "MEDIA_ROOT": Path(self.temp_dir.name) / "media",
                "TESTING": True,
                "SECRET_KEY": "flask-feature-tests",
                "SESSION_COOKIE_SECURE": False,
                "PUBLIC_BASE_URL": "https://gaminghub.example.test",
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_users(self):
        connection = sqlite3.connect(self.database_path)
        try:
            start = connection.execute(
                "SELECT COALESCE(MAX(id), 0) + 1 FROM auth_user"
            ).fetchone()[0]
            for offset, username in enumerate(("flask_test_player", "flask_test_staff")):
                connection.execute(
                    """
                    INSERT INTO auth_user
                        (id, password, last_login, is_superuser, username, last_name,
                         email, is_staff, is_active, date_joined, first_name)
                    VALUES (?, ?, NULL, 0, ?, '', ?, ?, 1, CURRENT_TIMESTAMP, '')
                    """,
                    (
                        start + offset,
                        generate_password_hash("correct-horse-battery"),
                        username,
                        f"{username}@example.test",
                        int(username.endswith("staff")),
                    ),
                )
            connection.commit()
            return start, start + 1
        finally:
            connection.close()

    def _runtime_query(self, query, parameters=()):
        connection = sqlite3.connect(self.app.config["GAME_DATABASE"])
        try:
            return connection.execute(query, parameters).fetchone()
        finally:
            connection.close()

    def _create_tournament(self):
        connection = sqlite3.connect(self.database_path)
        try:
            game_id = connection.execute(
                "SELECT id FROM tournament_game ORDER BY id LIMIT 1"
            ).fetchone()[0]
            cursor = connection.execute(
                """
                INSERT INTO tournament_tournament
                    (title, description, entry_fee, max_participants, current_participants,
                     start_date, end_date, status, rules, created_at, updated_at, game_id,
                     created_by_id, currency, format, registration_deadline, requirements,
                     social_media_links, stream_url, game_prize)
                VALUES
                    ('Flask Test Cup', 'Integration test tournament', 5, 8, 0,
                     '2027-01-01 00:00:00', '2027-01-02 00:00:00', 'upcoming', '',
                     CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, ?, ?, 'USD', 'single_elimination',
                     '2026-12-31 00:00:00', '', '{}', '', 25)
                """,
                (game_id, self.user_ids[0]),
            )
            connection.commit()
            return cursor.lastrowid
        finally:
            connection.close()

    def _csrf(self):
        with self.client.session_transaction() as stored:
            return stored["csrf_token"]

    def _login(self, index=0):
        self.client.get("/login/")
        with patch.dict("os.environ", {"ADMIN_EMAIL": ""}):
            response = self.client.post(
                "/login/",
                data={
                    "username": ("flask_test_player", "flask_test_staff")[index],
                    "password": "correct-horse-battery",
                    "csrf_token": self._csrf(),
                },
            )
        self.assertEqual(response.status_code, 302)

    def _database(self, query, parameters=()):
        connection = sqlite3.connect(self.database_path)
        try:
            return connection.execute(query, parameters).fetchone()
        finally:
            connection.close()

    def _create_original_room(self, game, title="Original game test"):
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                """
                INSERT INTO core_room
                    (title, description, game, is_active, created_at, host_id,
                     game_password, room_code, status, max_players)
                VALUES (?, '', ?, 1, CURRENT_TIMESTAMP, ?,
                        NULL, ?, 'waiting', 4)
                """,
                (title, game, self.user_ids[0], f"ORIG{game[-1]}"),
            )
            connection.commit()
            return f"ORIG{game[-1]}"
        finally:
            connection.close()

    def _authenticate_client(self, client, user_id, token):
        with client.session_transaction() as stored:
            stored["user_id"] = user_id
            stored["csrf_token"] = token

    def test_login_room_creation_and_joining(self):
        self._login()
        with patch("flask_app.feature_auth.send_email") as send_email:
            response = self.client.post(
                "/rooms/create/",
                data={
                    "csrf_token": self._csrf(),
                    "title": "Test match",
                    "game": "FIFA",
                    "description": "A Flask integration test.",
                    "max_players": "4",
                    "game_password": "",
                },
            )
        self.assertEqual(response.status_code, 302)
        room_url = response.headers["Location"]
        room_code = room_url.rstrip("/").rsplit("/", 1)[-1]
        send_email.assert_called_once()
        self.assertIn(room_code, send_email.call_args.args[2])
        self.assertIsNotNone(
            self._database("SELECT id FROM core_room WHERE room_code = ?", (room_code,))
        )
        self.assertIsNotNone(
            self._database(
                """
                SELECT game_rooms.id
                FROM core_game_rooms AS game_rooms
                JOIN core_game AS game ON game.id = game_rooms.game_id
                JOIN core_room AS room ON room.id = game_rooms.room_id
                WHERE game.name = 'FIFA Mobile' AND room.room_code = ?
                """,
                (room_code,),
            )
        )

        guest = self.app.test_client()
        with guest.session_transaction() as stored:
            stored["csrf_token"] = "guest-csrf"
        guest.post(
            "/login/",
            data={
                "username": "flask_test_player",
                "password": "correct-horse-battery",
                "csrf_token": "guest-csrf",
            },
        )
        with guest.session_transaction() as stored:
            guest_id = stored["user_id"]
        host_id = self._database(
            "SELECT host_id FROM core_room WHERE room_code = ?", (room_code,)
        )[0]
        if guest_id == host_id:
            second_user = self.user_ids[1]
            with guest.session_transaction() as stored:
                stored["user_id"] = second_user
                stored["csrf_token"] = "guest-csrf"
        response = guest.post(
            f"/rooms/{room_code}/join/",
            data={"csrf_token": "guest-csrf", "game_password": ""},
        )
        self.assertEqual(response.status_code, 302)
        joined_id = self._database(
            "SELECT user_id FROM core_room_players WHERE room_id = "
            "(SELECT id FROM core_room WHERE room_code = ?)",
            (room_code,),
        )[0]
        self.assertNotEqual(joined_id, host_id)

    def test_game_detail_includes_existing_rooms_with_room_game_aliases(self):
        self._create_original_room("FIFA", title="FIFA 24 Pro Clubs")
        response = self.client.get("/games/1/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"FIFA 24 Pro Clubs", response.data)

    def test_neon_sprint_is_shared_and_first_to_goal_wins(self):
        self._login()
        room_code = self._create_original_room("HUB_NEON_SPRINT")
        response = self.client.get(f"/rooms/{room_code}/play/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Neon Sprint", response.data)

        guest = self.app.test_client()
        self._authenticate_client(guest, self.user_ids[1], "guest-token")
        response = guest.post(
            f"/rooms/{room_code}/join/",
            data={"csrf_token": "guest-token", "game_password": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            guest.post(
                f"/rooms/{room_code}/play/start/",
                data={"csrf_token": "guest-token"},
            ).status_code,
            403,
        )

        response = self.client.post(
            f"/rooms/{room_code}/play/start/",
            data={"csrf_token": self._csrf()},
        )
        self.assertEqual(response.status_code, 302)
        state = guest.get(f"/api/rooms/{room_code}/game/").get_json()
        self.assertEqual(state["status"], "playing")
        self.assertEqual({player["username"] for player in state["players"]}, {
            "flask_test_player",
            "flask_test_staff",
        })

        connection = sqlite3.connect(self.app.config["GAME_DATABASE"])
        try:
            connection.execute(
                "UPDATE live_game_player SET score = 24 WHERE room_code = ? AND user_id = ?",
                (room_code, self.user_ids[0]),
            )
            connection.commit()
        finally:
            connection.close()
        response = self.client.post(
            f"/api/rooms/{room_code}/game/action/",
            data={"csrf_token": self._csrf(), "action": "boost"},
        )
        self.assertEqual(response.get_json()["status"], "finished")
        state = guest.get(f"/api/rooms/{room_code}/game/").get_json()
        self.assertEqual(state["players"][0]["score"], 25)
        runtime = sqlite3.connect(self.app.config["GAME_DATABASE"])
        try:
            recorded = runtime.execute(
                """
                SELECT user_id, score, won FROM live_game_result
                WHERE room_code = ? ORDER BY user_id
                """,
                (room_code,),
            ).fetchall()
        finally:
            runtime.close()
        self.assertEqual(recorded, [(self.user_ids[0], 25, 1), (self.user_ids[1], 0, 0)])
        self.assertEqual(
            self.client.get("/originals/neon-sprint/leaderboard/").status_code,
            200,
        )
        leaderboard = self.client.get("/originals/leaderboard/")
        self.assertEqual(leaderboard.status_code, 200)
        self.assertIn(b"flask_test_player", leaderboard.data)
        self.assertIn(b"100.0%", leaderboard.data)
        self.client.get(f"/api/rooms/{room_code}/game/")
        self.assertEqual(
            self._runtime_query(
                "SELECT COUNT(*) FROM live_game_result WHERE room_code = ?",
                (room_code,),
            )[0],
            2,
        )

    def test_cipher_clash_checks_answers_and_updates_shared_challenge(self):
        self._login()
        room_code = self._create_original_room("HUB_CIPHER_CLASH")
        guest = self.app.test_client()
        self._authenticate_client(guest, self.user_ids[1], "guest-token")
        guest.post(
            f"/rooms/{room_code}/join/",
            data={"csrf_token": "guest-token", "game_password": ""},
        )
        self.client.post(
            f"/rooms/{room_code}/play/start/",
            data={"csrf_token": self._csrf()},
        )

        state = guest.get(f"/api/rooms/{room_code}/game/").get_json()
        self.assertNotIn("secret", state["challenge"])
        runtime = sqlite3.connect(self.app.config["GAME_DATABASE"])
        try:
            answer = runtime.execute(
                "SELECT json_extract(challenge, '$.secret') FROM live_game_round WHERE room_code = ?",
                (room_code,),
            ).fetchone()[0]
        finally:
            runtime.close()
        invalid = guest.post(
            f"/api/rooms/{room_code}/game/action/",
            data={"csrf_token": "guest-token", "guess": "1123"},
        )
        self.assertEqual(invalid.status_code, 400)
        wrong_guess = "".join(str((int(digit) + 5) % 10) for digit in answer)
        response = guest.post(
            f"/api/rooms/{room_code}/game/action/",
            data={"csrf_token": "guest-token", "guess": wrong_guess},
        )
        self.assertFalse(response.get_json()["solved"])
        self.assertNotIn("secret", guest.get(
            f"/api/rooms/{room_code}/game/"
        ).get_json()["challenge"])
        runtime = sqlite3.connect(self.app.config["GAME_DATABASE"])
        try:
            runtime.execute(
                "UPDATE live_game_player SET last_action_at = 0 WHERE room_code = ? AND user_id = ?",
                (room_code, self.user_ids[1]),
            )
            runtime.commit()
        finally:
            runtime.close()
        response = guest.post(
            f"/api/rooms/{room_code}/game/action/",
            data={"csrf_token": "guest-token", "guess": answer},
        )
        self.assertTrue(response.get_json()["solved"])
        state = self.client.get(f"/api/rooms/{room_code}/game/").get_json()
        guest_score = next(
            player["score"]
            for player in state["players"]
            if player["user_id"] == self.user_ids[1]
        )
        self.assertEqual(guest_score, 1)
        runtime = sqlite3.connect(self.app.config["GAME_DATABASE"])
        try:
            result = runtime.execute(
                """
                SELECT user_id, score, won FROM live_game_result
                WHERE room_code = ? AND user_id = ?
                """,
                (room_code, self.user_ids[1]),
            ).fetchone()
        finally:
            runtime.close()
        self.assertEqual(result, (self.user_ids[1], 1, 1))

    def test_expired_tied_match_is_recorded_once_as_a_draw(self):
        self._login()
        room_code = self._create_original_room("HUB_NEON_SPRINT")
        guest = self.app.test_client()
        self._authenticate_client(guest, self.user_ids[1], "guest-token")
        guest.post(
            f"/rooms/{room_code}/join/",
            data={"csrf_token": "guest-token", "game_password": ""},
        )
        self.client.post(
            f"/rooms/{room_code}/play/start/",
            data={"csrf_token": self._csrf()},
        )
        runtime = sqlite3.connect(self.app.config["GAME_DATABASE"])
        try:
            runtime.execute(
                "UPDATE live_game_player SET score = 5 WHERE room_code = ?",
                (room_code,),
            )
            runtime.execute(
                "UPDATE live_game_round SET ends_at = 0 WHERE room_code = ?",
                (room_code,),
            )
            runtime.commit()
        finally:
            runtime.close()

        state = guest.get(f"/api/rooms/{room_code}/game/").get_json()
        self.assertEqual(state["status"], "finished")
        self.client.get(f"/api/rooms/{room_code}/game/")
        self.assertEqual(
            self._runtime_query(
                "SELECT COUNT(*), SUM(won) FROM live_game_result WHERE room_code = ?",
                (room_code,),
            ),
            (2, 0),
        )

    def test_tactic_grid_enforces_turns_and_connect_four_win(self):
        self._login()
        room_code = self._create_original_room("HUB_TACTIC_GRID")
        guest = self.app.test_client()
        self._authenticate_client(guest, self.user_ids[1], "guest-token")
        response = guest.post(
            f"/rooms/{room_code}/join/",
            data={"csrf_token": "guest-token", "game_password": ""},
        )
        self.assertEqual(response.status_code, 302)
        self.client.post(
            f"/rooms/{room_code}/play/start/",
            data={"csrf_token": self._csrf()},
        )

        clients = {
            self.user_ids[0]: (self.client, self._csrf()),
            self.user_ids[1]: (guest, "guest-token"),
        }
        first_player = self.client.get(
            f"/api/rooms/{room_code}/game/"
        ).get_json()["challenge"]["first_player"]
        wrong_client = clients[self.user_ids[1] if first_player == self.user_ids[0] else self.user_ids[0]][0]
        wrong_token = clients[self.user_ids[1] if first_player == self.user_ids[0] else self.user_ids[0]][1]
        rejected = wrong_client.post(
            f"/api/rooms/{room_code}/game/action/",
            data={"csrf_token": wrong_token, "column": 0},
        )
        self.assertEqual(rejected.status_code, 409)

        winner_id = first_player
        for column in (0, 1, 0, 1, 0, 1, 0):
            state = self.client.get(
                f"/api/rooms/{room_code}/game/"
            ).get_json()
            active_client, token = clients[state["challenge"]["current_turn"]]
            response = active_client.post(
                f"/api/rooms/{room_code}/game/action/",
                data={"csrf_token": token, "column": column},
            )
        self.assertEqual(response.get_json()["status"], "finished")
        state = self.client.get(f"/api/rooms/{room_code}/game/").get_json()
        self.assertEqual(state["challenge"]["winner"], winner_id)
        self.assertEqual([row[0] for row in state["challenge"]["board"][-4:]], ["X"] * 4)

    def test_reaction_relay_penalizes_false_start_and_rewards_signal(self):
        self._login()
        room_code = self._create_original_room("HUB_REACTION_RELAY")
        guest = self.app.test_client()
        self._authenticate_client(guest, self.user_ids[1], "guest-token")
        guest.post(
            f"/rooms/{room_code}/join/",
            data={"csrf_token": "guest-token", "game_password": ""},
        )
        self.client.post(
            f"/rooms/{room_code}/play/start/",
            data={"csrf_token": self._csrf()},
        )

        early = self.client.post(
            f"/api/rooms/{room_code}/game/action/",
            data={"csrf_token": self._csrf(), "action": "react"},
        )
        self.assertTrue(early.get_json()["false_start"])
        runtime = sqlite3.connect(self.app.config["GAME_DATABASE"])
        try:
            challenge = runtime.execute(
                "SELECT challenge FROM live_game_round WHERE room_code = ?",
                (room_code,),
            ).fetchone()[0]
            data = json.loads(challenge)
            data["signal_at"] = 0
            runtime.execute(
                "UPDATE live_game_round SET challenge = ? WHERE room_code = ?",
                (json.dumps(data), room_code),
            )
            runtime.execute(
                "UPDATE live_game_player SET last_action_at = 0 WHERE room_code = ? AND user_id = ?",
                (room_code, self.user_ids[0]),
            )
            runtime.commit()
        finally:
            runtime.close()
        result = self.client.post(
            f"/api/rooms/{room_code}/game/action/",
            data={"csrf_token": self._csrf(), "action": "react"},
        )
        self.assertEqual(result.get_json()["status"], "playing")
        state = self.client.get(f"/api/rooms/{room_code}/game/").get_json()
        host_score = next(
            player["score"]
            for player in state["players"]
            if player["user_id"] == self.user_ids[0]
        )
        self.assertEqual(host_score, 1)

    def test_login_notifies_configured_admin(self):
        self.client.get("/login/")
        with patch.dict("os.environ", {"ADMIN_EMAIL": "admin@example.test"}):
            with patch("flask_app.feature_auth.send_email") as send_email:
                response = self.client.post(
                    "/login/",
                    data={
                        "username": "flask_test_player",
                        "password": "correct-horse-battery",
                        "csrf_token": self._csrf(),
                    },
                )
        self.assertEqual(response.status_code, 302)
        send_email.assert_called_once()
        self.assertEqual(
            send_email.call_args.args[0], "admin@example.test"
        )
        self.assertIn("flask_test_player", send_email.call_args.args[2])

    def test_original_game_can_be_created_and_launched_from_room_lobby(self):
        self._login()
        with patch("flask_app.feature_auth.send_email"):
            response = self.client.post(
                "/rooms/create/",
                data={
                    "csrf_token": self._csrf(),
                    "title": "Neon room",
                    "game": "HUB_NEON_SPRINT",
                    "description": "",
                    "max_players": "4",
                    "game_password": "",
                },
            )
        self.assertEqual(response.status_code, 302)
        room_code = response.headers["Location"].rstrip("/").rsplit("/", 1)[-1]
        room = self._database(
            "SELECT game FROM core_room WHERE room_code = ?", (room_code,)
        )
        self.assertEqual(room[0], "HUB_NEON_SPRINT")
        detail = self.client.get(f"/rooms/{room_code}/")
        self.assertIn(b"Open game lobby", detail.data)
        self.assertIn(b"Start the game", detail.data)
        originals = self.client.get("/originals/")
        self.assertIn(b"Neon Sprint", originals.data)
        self.assertIn(b"Cipher Clash", originals.data)

    def test_existing_pbkdf2_sha256_password_hash_remains_valid(self):
        password = "legacy-password"
        salt = "stable-test-salt"
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt.encode("utf-8"), 600000
        )
        encoded = "pbkdf2_sha256$600000$" + salt + "$" + base64.b64encode(digest).decode("ascii")
        self.assertTrue(_verify_password(encoded, password))
        self.assertFalse(_verify_password(encoded, "not-the-password"))

    def test_registration_creates_a_flask_login_compatible_user(self):
        self.client.get("/register/")
        with patch.dict(
            "os.environ",
            {
                "MAIL_SERVER": "",
                "MAIL_USERNAME": "",
                "MAIL_PASSWORD": "",
                "MAIL_DEFAULT_SENDER": "",
            },
        ):
            response = self.client.post(
                "/register/",
                data={
                    "csrf_token": self._csrf(),
                    "username": "new_flask_player",
                    "email": "new_flask_player@example.test",
                    "password": "new-player-password",
                    "password_confirm": "new-player-password",
                },
            )
        self.assertEqual(response.status_code, 302)
        new_user_id = self._database(
            "SELECT id FROM auth_user WHERE username = ?",
            ("new_flask_player",),
        )[0]
        self.assertIsNotNone(
            self._database(
                "SELECT id FROM core_userprofile WHERE user_id = ?", (new_user_id,)
            )
        )
        self.assertEqual(self.client.get("/rooms/").status_code, 200)

    def test_stats_submission_is_pending_until_review(self):
        self._login()
        response = self.client.post(
            "/submit/fifa/",
            data={
                "csrf_token": self._csrf(),
                "goals": "4",
                "assists": "2",
                "wins": "3",
                "matches_played": "5",
                "description": "Test match",
            },
        )
        self.assertEqual(response.status_code, 302)
        submission = self._database(
            "SELECT status, verified, goals FROM core_statsubmission WHERE user_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (self.user_ids[0],),
        )
        self.assertEqual(submission, ("pending", 0, 4))

    def test_stats_proof_upload_is_saved_under_configured_media_root(self):
        self._login()
        image = io.BytesIO()
        Image.new("RGB", (1, 1), "blue").save(image, format="PNG")
        image.seek(0)
        response = self.client.post(
            "/submit/fifa/",
            data={
                "csrf_token": self._csrf(),
                "goals": "1",
                "assists": "0",
                "wins": "1",
                "matches_played": "1",
                "screenshot": (image, "proof.png"),
            },
        )
        self.assertEqual(response.status_code, 302)
        proof = self._database(
            "SELECT screenshot FROM core_statsubmission WHERE user_id = ? "
            "ORDER BY id DESC LIMIT 1",
            (self.user_ids[0],),
        )[0]
        self.assertTrue((Path(self.temp_dir.name) / "media" / proof).is_file())

    def test_payment_review_updates_participant_count(self):
        self._login()
        payment_url = f"/tournament/{self.tournament_id}/payment/submit/"
        proof = io.BytesIO()
        Image.new("RGB", (1, 1), "red").save(proof, format="PNG")
        proof.seek(0)
        response = self.client.post(
            payment_url,
            data={
                "csrf_token": self._csrf(),
                "payment_method": "mobile_money",
                "payment_proof": (proof, "receipt.png"),
            },
        )
        self.assertEqual(response.status_code, 302)
        subscription_id = self._database(
            "SELECT id FROM tournament_tournamentsubscription WHERE user_id = ? AND tournament_id = ?",
            (self.user_ids[0], self.tournament_id),
        )[0]
        self.assertEqual(
            self._database(
                "SELECT payment_status FROM tournament_tournamentsubscription WHERE id = ?",
                (subscription_id,),
            )[0],
            "pending",
        )
        proof_path = self._database(
            "SELECT payment_proof FROM tournament_tournamentsubscription WHERE id = ?",
            (subscription_id,),
        )[0]
        self.assertTrue((Path(self.temp_dir.name) / "media" / proof_path).is_file())

        self.client.post("/logout/", data={"csrf_token": self._csrf()})
        self._login(index=1)
        self.assertEqual(self.client.get("/admin/").status_code, 200)
        response = self.client.post(
            f"/admin/payments/{subscription_id}/status/",
            data={"csrf_token": self._csrf(), "status": "completed"},
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            f"/admin/tournaments/{self.tournament_id}/status/",
            data={"csrf_token": self._csrf(), "status": "completed"},
        )
        self.assertEqual(response.status_code, 302)
        response = self.client.post(
            f"/admin/tournaments/{self.tournament_id}/results/",
            data={
                "csrf_token": self._csrf(),
                "first_place_id": str(self.user_ids[0]),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self._database(
                "SELECT first_place_id FROM tournament_tournamentresult "
                "WHERE tournament_id = ?",
                (self.tournament_id,),
            )[0],
            self.user_ids[0],
        )
        results = self.client.get(f"/tournament/{self.tournament_id}/results/")
        self.assertEqual(results.status_code, 200)
        self.assertIn(b"flask_test_player", results.data)
        self.assertEqual(
            self._database(
                "SELECT current_participants FROM tournament_tournament WHERE id = ?",
                (self.tournament_id,),
            )[0],
            1,
        )

    def test_admin_can_update_match_results(self):
        connection = sqlite3.connect(self.database_path)
        try:
            cursor = connection.execute(
                """
                INSERT INTO tournament_match
                    (round_number, match_number, scheduled_time, status,
                     score_player1, score_player2, player1_id, player2_id,
                     tournament_id, winner_id)
                VALUES (1, 1, NULL, 'scheduled', 0, 0, ?, ?, ?, NULL)
                """,
                (*self.user_ids, self.tournament_id),
            )
            connection.commit()
            match_id = cursor.lastrowid
        finally:
            connection.close()

        self._login(index=1)
        response = self.client.post(
            f"/admin/matches/{match_id}/",
            data={
                "csrf_token": self._csrf(),
                "status": "completed",
                "score_player1": "3",
                "score_player2": "1",
                "winner_id": str(self.user_ids[0]),
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self._database(
                "SELECT status, score_player1, score_player2, winner_id "
                "FROM tournament_match WHERE id = ?",
                (match_id,),
            ),
            ("completed", 3, 1, self.user_ids[0]),
        )

    def test_admin_can_manage_users_and_rooms_safely(self):
        room_code = self._create_original_room("HUB_NEON_SPRINT")
        room_id = self._database(
            "SELECT id FROM core_room WHERE room_code = ?", (room_code,)
        )[0]
        self._login(index=1)

        dashboard = self.client.get("/admin/?q=flask_test_player")
        self.assertEqual(dashboard.status_code, 200)
        self.assertIn(b"User management", dashboard.data)
        self.assertIn(b"Room management", dashboard.data)
        self.assertIn(b"flask_test_player", dashboard.data)
        self.assertNotIn(b"flask_test_staff</td>", dashboard.data)

        role_change = self.client.post(
            f"/admin/users/{self.user_ids[0]}/",
            data={"csrf_token": self._csrf(), "action": "grant_staff"},
        )
        self.assertEqual(role_change.status_code, 403)
        self.assertEqual(
            self._database(
                "SELECT is_staff FROM auth_user WHERE id = ?", (self.user_ids[0],)
            )[0],
            0,
        )

        disabled = self.client.post(
            f"/admin/users/{self.user_ids[0]}/",
            data={"csrf_token": self._csrf(), "action": "deactivate"},
        )
        self.assertEqual(disabled.status_code, 302)
        self.assertEqual(
            self._database(
                "SELECT is_active FROM auth_user WHERE id = ?", (self.user_ids[0],)
            )[0],
            0,
        )
        activated = self.client.post(
            f"/admin/users/{self.user_ids[0]}/",
            data={"csrf_token": self._csrf(), "action": "activate"},
        )
        self.assertEqual(activated.status_code, 302)
        self.assertEqual(
            self._database(
                "SELECT is_active FROM auth_user WHERE id = ?", (self.user_ids[0],)
            )[0],
            1,
        )
        self_deactivation = self.client.post(
            f"/admin/users/{self.user_ids[1]}/",
            data={"csrf_token": self._csrf(), "action": "deactivate"},
        )
        self.assertEqual(self_deactivation.status_code, 400)

        closed = self.client.post(
            f"/admin/rooms/{room_id}/status/",
            data={"csrf_token": self._csrf(), "is_active": "0"},
        )
        self.assertEqual(closed.status_code, 302)
        self.assertEqual(
            self._database(
                "SELECT is_active FROM core_room WHERE id = ?", (room_id,)
            )[0],
            0,
        )

    def test_superuser_can_grant_staff_access(self):
        connection = sqlite3.connect(self.database_path)
        try:
            connection.execute(
                "UPDATE auth_user SET is_superuser = 1 WHERE id = ?",
                (self.user_ids[1],),
            )
            connection.commit()
        finally:
            connection.close()
        self._login(index=1)
        response = self.client.post(
            f"/admin/users/{self.user_ids[0]}/",
            data={"csrf_token": self._csrf(), "action": "grant_staff"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            self._database(
                "SELECT is_staff FROM auth_user WHERE id = ?", (self.user_ids[0],)
            )[0],
            1,
        )

    def test_password_reset_token_can_be_used_once(self):
        user_id = self.user_ids[0]
        user = self._database(
            "SELECT id, password FROM auth_user WHERE id = ?", (user_id,)
        )
        with self.app.app_context():
            token = _password_reset_token({"id": user[0], "password": user[1]})
        url = (
            f"/password-reset-confirm/{_reset_uid(user_id)}/{token}/"
        )
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        response = self.client.post(
            url,
            data={
                "csrf_token": self._csrf(),
                "password": "new-test-password",
                "password_confirm": "new-test-password",
            },
        )
        self.assertEqual(response.status_code, 302)
        new_hash = self._database(
            "SELECT password FROM auth_user WHERE id = ?", (user_id,)
        )[0]
        self.assertTrue(check_password_hash(new_hash, "new-test-password"))
        self.assertEqual(self.client.get(url).status_code, 400)

    def test_csrf_token_is_required_for_state_changing_requests(self):
        response = self.client.post("/contact/", data={"name": "Test"})
        self.assertEqual(response.status_code, 400)

    def test_contact_form_reports_missing_email_configuration(self):
        self.client.get("/contact/")
        with patch.dict(
            "os.environ",
            {
                "MAIL_SERVER": "",
                "MAIL_USERNAME": "",
                "MAIL_PASSWORD": "",
                "MAIL_DEFAULT_SENDER": "",
            },
        ):
            response = self.client.post(
                "/contact/",
                data={
                    "csrf_token": self._csrf(),
                    "name": "Test User",
                    "email": "test@example.test",
                    "subject": "support",
                    "message": "I need help with a test.",
                },
            )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"message was not sent", response.data)


if __name__ == "__main__":
    unittest.main()
