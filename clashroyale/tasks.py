# clashroyale/tasks.py
from django.utils import timezone
from datetime import timedelta
from .models import ClashRoyalePlayer
from .services import ClashRoyaleAPI


def update_all_players():
    """Background task to update all Clash Royale players"""
    api = ClashRoyaleAPI()

    # Only update players updated more than 15 minutes ago
    cutoff = timezone.now() - timedelta(minutes=15)
    players = ClashRoyalePlayer.objects.filter(last_updated__lt=cutoff)

    for player in players:
        player_data = api.get_player_info(player.player_tag)
        if player_data:
            # Update player stats
            player.trophies = player_data.get('trophies', 0)
            # ... update other fields
            player.save()

            # Update leaderboard
            update_leaderboard_entry(player)