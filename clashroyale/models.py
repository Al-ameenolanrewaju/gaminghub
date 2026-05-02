# clashroyale/models.py
from django.db import models
from django.contrib.auth.models import User
import random
from datetime import datetime


class ClashRoyalePlayer(models.Model):
    """Clash Royale player with mock/real data support"""
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='clash_royale_players')
    player_tag = models.CharField(max_length=20, unique=True)
    player_name = models.CharField(max_length=100)

    # Stats
    trophies = models.IntegerField(default=0)
    best_trophies = models.IntegerField(default=0)
    level = models.IntegerField(default=1)

    # Battle stats
    wins = models.IntegerField(default=0)
    losses = models.IntegerField(default=0)
    draws = models.IntegerField(default=0)
    total_battles = models.IntegerField(default=0)
    win_rate = models.FloatField(default=0.0)

    # Clan
    clan_name = models.CharField(max_length=100, blank=True)
    clan_tag = models.CharField(max_length=20, blank=True)

    # Meta
    is_mock = models.BooleanField(default=True)  # Mark as mock data
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def update_win_rate(self):
        if self.total_battles > 0:
            self.win_rate = (self.wins / self.total_battles) * 100
        self.save()

    def _str_(self):
        return f"{self.player_name} ({self.player_tag}) - {self.trophies}🏆"

    @staticmethod
    def generate_mock_data(player_tag):
        """Generate realistic mock data for a player"""
        # Use player_tag as seed for consistency
        seed = sum(ord(c) for c in player_tag)
        random.seed(seed)

        names = ["RoyalePro", "ClashMaster", "TrophyHunter", "CrownChaser",
                 "DragonRider", "WizardKing", "GoblinSlayer", "ElixirLord"]

        clans = ["Reddit Alpha", "Competitive", "Legend League", "Top Players",
                 "Global Elite", "Pro Clan", "Tournament", "Champions"]

        trophies = random.randint(4000, 7500)
        wins = random.randint(100, 2500)
        losses = random.randint(50, 2000)
        draws = random.randint(10, 500)
        total = wins + losses + draws

        return {
            'player_name': f"{random.choice(names)}{random.randint(1, 999)}",
            'trophies': trophies,
            'best_trophies': trophies + random.randint(0, 500),
            'level': random.randint(8, 15),
            'wins': wins,
            'losses': losses,
            'draws': draws,
            'total_battles': total,
            'win_rate': (wins / total * 100) if total > 0 else 0,
            'clan_name': random.choice(clans),
            'clan_tag': f"#CLAN{random.randint(100, 999)}",
            'is_mock': True,
        }