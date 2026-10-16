import os
import secrets
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent

DATABASE = Path(os.environ.get("GAMING_HUB_DATABASE", BASE_DIR / "db.sqlite3"))
if not DATABASE.is_absolute():
    DATABASE = BASE_DIR / DATABASE

GAME_DATABASE = Path(
    os.environ.get("GAMING_HUB_GAME_DATABASE", BASE_DIR / "instance" / "live_games.sqlite3")
)
if not GAME_DATABASE.is_absolute():
    GAME_DATABASE = BASE_DIR / GAME_DATABASE

DEBUG = os.environ.get("FLASK_DEBUG") == "1"
MAX_CONTENT_LENGTH = 12 * 1024 * 1024
MEDIA_ROOT = Path(os.environ.get("GAMING_HUB_MEDIA_ROOT", BASE_DIR / "media"))
SECRET_KEY = (
    os.environ.get("FLASK_SECRET_KEY")
    or os.environ.get("SECRET_KEY")
    or secrets.token_hex(32)
)
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SECURE = os.environ.get("FLASK_COOKIE_SECURE", "false").lower() == "true"
CLASH_ROYALE_API_KEY = os.environ.get("CLASH_ROYALE_API_KEY", "")
USE_MOCK_DATA = os.environ.get("USE_MOCK_DATA", "true").lower() == "true"
