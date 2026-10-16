import re


_ROOM_GAME_ALIASES = {
    "fifamobile": ("FIFA", "FIFA_MOBILE"),
    "pubgmobile": ("PUBG", "PUBG_MOBILE"),
    "clashofclans": ("COC", "CLASH_OF_CLANS"),
}


def _normalize_game_name(value):
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def room_game_labels(game_name):
    aliases = _ROOM_GAME_ALIASES.get(_normalize_game_name(game_name), ())
    return (game_name, *aliases)


def catalog_game_id(database, room_game):
    normalized_room_game = _normalize_game_name(room_game)
    games = database.execute("SELECT id, name FROM core_game").fetchall()
    for game in games:
        if any(
            normalized_room_game == _normalize_game_name(label)
            for label in room_game_labels(game["name"])
        ):
            return game["id"]
    return None
