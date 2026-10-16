from flask import Blueprint, abort, current_app, render_template, send_from_directory

from . import PROJECT_ROOT, get_db
from .game_rooms import room_game_labels


main = Blueprint("main", __name__)


@main.get("/media/<path:filename>")
def media_file(filename):
    return send_from_directory(current_app.config["MEDIA_ROOT"], filename)


@main.get("/")
def home():
    database = get_db()
    featured_games = database.execute(
        """
        SELECT id, name, genre, description, cover_image
        FROM core_game
        WHERE is_featured = 1
        ORDER BY created_at DESC
        LIMIT 6
        """
    ).fetchall()
    active_rooms = database.execute(
        """
        SELECT room.id, room.title, room.description, room.game, room.room_code, room.max_players,
               host.username AS host_username,
               (SELECT COUNT(*) FROM core_room_players AS players
                WHERE players.room_id = room.id) + 1 AS current_players
        FROM core_room AS room
        JOIN auth_user AS host ON host.id = room.host_id
        WHERE room.is_active = 1
        ORDER BY room.created_at DESC
        LIMIT 6
        """
    ).fetchall()
    return render_template(
        "home.html", featured_games=featured_games, active_rooms=active_rooms
    )


@main.get("/games/")
def game_list():
    games = get_db().execute(
        """
        SELECT id, name, genre, platform, description, cover_image, release_year
        FROM core_game
        ORDER BY created_at DESC
        """
    ).fetchall()
    return render_template("games.html", games=games)


@main.get("/games/<int:game_id>/")
def game_detail(game_id):
    database = get_db()
    game = database.execute(
        """
        SELECT id, name, genre, platform, description, cover_image,
               release_year, developer, official_website
        FROM core_game
        WHERE id = ?
        """,
        (game_id,),
    ).fetchone()
    if game is None:
        abort(404)

    rooms = database.execute(
        """
        SELECT DISTINCT room.id, room.title, room.game, room.room_code,
               host.username AS host_username
        FROM core_room AS room
        JOIN auth_user AS host ON host.id = room.host_id
        LEFT JOIN core_game_rooms AS game_rooms ON game_rooms.room_id = room.id
        WHERE room.is_active = 1
          AND (
              game_rooms.game_id = ?
              OR room.game COLLATE NOCASE IN ({})
          )
        ORDER BY room.created_at DESC
        LIMIT 5
        """.format(", ".join("?" for _ in room_game_labels(game["name"]))),
        (game_id, *room_game_labels(game["name"])),
    ).fetchall()
    reviews = database.execute(
        """
        SELECT review.rating, review.title, review.content, user.username
        FROM core_review AS review
        JOIN auth_user AS user ON user.id = review.user_id
        WHERE review.game_id = ?
        ORDER BY review.created_at DESC
        LIMIT 5
        """,
        (game_id,),
    ).fetchall()
    highlights = database.execute(
        """
        SELECT title, video_url, description
        FROM core_highlight
        WHERE game_id = ?
        ORDER BY created_at DESC
        LIMIT 3
        """,
        (game_id,),
    ).fetchall()
    return render_template(
        "game_detail.html", game=game, rooms=rooms, reviews=reviews, highlights=highlights
    )
