import sqlite3
import tempfile
import unittest
from pathlib import Path

from flask_app import create_app


class FlaskGameRoutesTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.database_path = Path(self.temp_dir.name) / "test.sqlite3"
        self._create_database()
        self.app = create_app(
            {
                "DATABASE": str(self.database_path),
                "GAME_DATABASE": str(Path(self.temp_dir.name) / "live_games.sqlite3"),
                "TESTING": True,
                "SECRET_KEY": "test-key",
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def _create_database(self):
        database = sqlite3.connect(self.database_path)
        try:
            database.executescript(
                """
                CREATE TABLE auth_user (id INTEGER PRIMARY KEY, username TEXT NOT NULL);
                CREATE TABLE core_game (
                    id INTEGER PRIMARY KEY, name TEXT NOT NULL, genre TEXT,
                    platform TEXT, description TEXT, cover_image TEXT,
                    release_year INTEGER, developer TEXT, official_website TEXT,
                    created_at TEXT, is_featured INTEGER NOT NULL DEFAULT 0
                );
                CREATE TABLE core_room (
                    id INTEGER PRIMARY KEY, title TEXT, description TEXT, game TEXT, room_code TEXT,
                    max_players INTEGER, is_active INTEGER, created_at TEXT, host_id INTEGER
                );
                CREATE TABLE core_room_players (id INTEGER PRIMARY KEY, room_id INTEGER, user_id INTEGER);
                CREATE TABLE core_game_rooms (id INTEGER PRIMARY KEY, game_id INTEGER, room_id INTEGER);
                CREATE TABLE core_review (
                    id INTEGER PRIMARY KEY, rating INTEGER, title TEXT, content TEXT,
                    user_id INTEGER, game_id INTEGER, created_at TEXT
                );
                CREATE TABLE core_highlight (
                    id INTEGER PRIMARY KEY, title TEXT, video_url TEXT, description TEXT,
                    created_at TEXT, game_id INTEGER
                );
                INSERT INTO auth_user (id, username) VALUES (1, 'player_one');
                INSERT INTO core_game
                    (id, name, genre, platform, description, created_at, is_featured)
                    VALUES (1, 'Example Arena', 'FPS', 'PC', 'A sample game.', '2025-01-01', 1);
                INSERT INTO core_room
                    (id, title, description, game, room_code, max_players, is_active, created_at, host_id)
                    VALUES (1, 'Evening Match', 'Bring your best strategy.', 'FPS', 'ABC123', 4, 1, '2025-01-02', 1);
                INSERT INTO core_game_rooms (id, game_id, room_id) VALUES (1, 1, 1);
                INSERT INTO core_review
                    (id, rating, title, content, user_id, game_id, created_at)
                    VALUES (1, 5, 'Great game', 'Fun with friends.', 1, 1, '2025-01-03');
                INSERT INTO core_highlight
                    (id, title, video_url, description, created_at, game_id)
                    VALUES (1, 'Match clip', 'https://example.test/clip', 'A close finish.', '2025-01-04', 1);
                """
            )
        finally:
            database.close()

    def test_home_displays_featured_game_and_active_room(self):
        response = self.client.get("/")

        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Example Arena", response.data)
        self.assertIn(b"Evening Match", response.data)
        self.assertIn(b"player_one", response.data)
        self.assertIn(b'href="/rooms/ABC123/"', response.data)
        self.assertIn(b"CONNECT. PLAY. DOMINATE.", response.data)
        self.assertIn(b"FEATURED GAMES", response.data)
        self.assertIn(b"ACTIVE GAME ROOMS", response.data)
        self.assertIn(b"GAMING HUB STATS", response.data)

    def test_game_list_and_detail_render_database_content(self):
        listing = self.client.get("/games/")
        detail = self.client.get("/games/1/")

        self.assertEqual(listing.status_code, 200)
        self.assertIn(b"Example Arena", listing.data)
        self.assertEqual(detail.status_code, 200)
        self.assertIn(b"Great game", detail.data)
        self.assertIn(b"Match clip", detail.data)
        self.assertIn(b"href=\"/rooms/ABC123/\"", detail.data)

    def test_unknown_game_returns_not_found(self):
        self.assertEqual(self.client.get("/games/999/").status_code, 404)


if __name__ == "__main__":
    unittest.main()
