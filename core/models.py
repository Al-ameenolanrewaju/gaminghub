
from django.urls import reverse
from django.db import models
from django.contrib.auth.models import User



class Game(models.Model):
    GENRES = [
        ('FOOTBALL', '⚽ Football'),
        ('FPS', '🔫 FPS (Call of Duty, PUBG)'),
        ('MOBA', '⚔ MOBA (Mobile Legends, LoL)'),
        ('BATTLE_ROYALE', '🎯 Battle Royale'),
        ('RACING', '🏎 Racing'),
        ('STRATEGY', '♟ Strategy'),
        ('SPORTS', '🏀 Other Sports'),
    ]

    PLATFORMS = [
        ('MOBILE', '📱 Mobile'),
        ('PC', '💻 PC'),
        ('CONSOLE', '🎮 Console'),
        ('CROSS', '🔄 Cross-Platform'),
    ]

    name = models.CharField(max_length=200)
    genre = models.CharField(max_length=20, choices=GENRES, default='FPS')
    platform = models.CharField(max_length=20, choices=PLATFORMS, default='MOBILE')
    description = models.TextField()
    cover_image = models.ImageField(upload_to='game_covers/', blank=True, null=True)
    release_year = models.IntegerField(null=True, blank=True)
    developer = models.CharField(max_length=100, blank=True)
    official_website = models.URLField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    is_featured = models.BooleanField(default=False)

    rooms = models.ManyToManyField('Room', related_name='games', blank=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse('game_detail', kwargs={'pk': self.pk})

    def get_genre_icon(self):
        icons = {
            'FOOTBALL': '⚽',
            'FPS': '🔫',
            'MOBA': '⚔',
            'BATTLE_ROYALE': '🎯',
            'RACING': '🏎',
            'STRATEGY': '♟',
            'SPORTS': '🏀',
        }
        return icons.get(self.genre, '🎮')


# core/models.py - Add this Room model
from django.db import models
from django.contrib.auth.models import User

# core/models.py - UPDATE Room model
import random
import string
from django.db import models
from django.contrib.auth.models import User


class Room(models.Model):
    # Game Choices - ALL POPULAR GAMES
    GAME_CHOICES = [
        # Mobile Games
        ('DLS', '⚽ Dream League Soccer'),
        ('PES', '🎮 eFootball PES'),
        ('COD_MOBILE', '🔫 Call of Duty Mobile'),
        ('FREEFIRE', '🔥 Free Fire'),
        ('PUBG_MOBILE', '🎯 PUBG Mobile'),

        # PC/Console Games
        ('FIFA', '🎮 FIFA 24'),
        ('COD', '🔫 Call of Duty'),
        ('FORTNITE', '🏹 Fortnite'),
        ('VALORANT', '💥 Valorant'),
        ('APEX', '⚡ Apex Legends'),
        ('MINECRAFT', '⛏️ Minecraft'),
        ('ROCKET_LEAGUE', '🚗 Rocket League'),

        # Other Games
        ('AMONG_US', '👽 Among Us'),
        ('ROBLOX', '🧱 Roblox'),
        ('GTA', '🚗 GTA Online'),
        ('NBA', '🏀 NBA 2K'),
    ]

    # Room Details
    title = models.CharField(max_length=100)
    description = models.TextField(max_length=500, blank=True)
    game = models.CharField(max_length=50, choices=GAME_CHOICES)

    # Room Code System (WORKS FOR ALL GAMES)
    room_code = models.CharField(max_length=8, unique=True, blank=True)
    game_password = models.CharField(max_length=10, blank=True, null=True)

    # Host & Players
    host = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hosted_rooms')
    players = models.ManyToManyField(User, related_name='joined_rooms', blank=True)
    max_players = models.IntegerField(default=4, choices=[(2, '2'), (4, '4'), (6, '6'), (8, '8'), (10, '10')])

    # Status
    is_active = models.BooleanField(default=True)
    status = models.CharField(max_length=20, default='waiting', choices=[
        ('waiting', '⏳ Waiting for players'),
        ('full', '✅ Room Full'),
        ('in_game', '🎮 In Game'),
        ('finished', '🏁 Game Finished'),
    ])

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.title} ({self.get_game_display()}) - {self.room_code}"

    def save(self, *args, **kwargs):
        # Generate unique room code if not set
        if not self.room_code:
            self.room_code = self.generate_room_code()
        super().save(*args, **kwargs)

    def generate_room_code(self):
        """Generate unique room code: 3 letters + 3 numbers"""
        while True:
            letters = ''.join(random.choices(string.ascii_uppercase, k=3))
            numbers = ''.join(random.choices(string.digits, k=3))
            code = f"{letters}{numbers}"

            # Check if code already exists
            if not Room.objects.filter(room_code=code).exists():
                return code

    def current_players_count(self):
        """Count total players in room (host + joined players)"""
        return self.players.count() + 1  # +1 for host

    def available_slots(self):
        """Calculate available slots"""
        return self.max_players - self.current_players_count()

    def is_full(self):
        """Check if room is full"""
        return self.current_players_count() >= self.max_players

    def can_user_join(self, user):
        """Check if user can join this room"""
        if user == self.host:
            return False  # Host is already in room
        if user in self.players.all():
            return False  # Already joined
        if self.is_full():
            return False  # Room is full
        if not self.is_active:
            return False  # Room not active
        return True

    def get_game_connection_info(self):
        """Get connection instructions for specific game"""
        game_info = {
            'DLS': {
                'steps': [
                    "Open Dream League Soccer",
                    "Tap 'Online' or 'Multiplayer'",
                    "Select 'Join Room'",
                    f"Enter Code: {self.room_code}",
                    f"Password: {self.game_password if self.game_password else 'None'}",
                    "Tap 'Connect'"
                ],
                'icon': '⚽'
            },
            'COD_MOBILE': {
                'steps': [
                    "Launch Call of Duty Mobile",
                    "Go to 'Multiplayer' → 'Private Match'",
                    f"Enter Room ID: {self.room_code}",
                    "Wait for host to start",
                    "Tap 'Ready' when prompted"
                ],
                'icon': '🔫'
            },
            'FORTNITE': {
                'steps': [
                    "Open Fortnite",
                    "Click 'Change Game Mode'",
                    "Select 'Creative' or 'Battle Lab'",
                    f"Enter Island Code: {self.room_code}",
                    "Click 'Accept'",
                    "Wait in lobby"
                ],
                'icon': '🏹'
            },
            'FIFA': {
                'steps': [
                    "Start FIFA game",
                    "Go to 'Online Friendlies'",
                    "Select 'Join Friends Match'",
                    f"Enter Session Code: {self.room_code}",
                    f"Password: {self.game_password if self.game_password else 'None'}",
                    "Press 'Join Match'"
                ],
                'icon': '🎮'
            },
            # Add more games as needed
        }

        # Default for any game
        default_info = {
            'steps': [
                f"Room Code: {self.room_code}",
                f"Password: {self.game_password if self.game_password else 'No password'}",
                "Enter this code in your game's multiplayer/online section",
                "Wait for host to start the game"
            ],
            'icon': '🎮'
        }

        return game_info.get(self.game, default_info)

class Team(models.Model):
    name = models.CharField(max_length=100)
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='teams')
    leader = models.ForeignKey(User, on_delete=models.CASCADE, related_name='led_teams')
    members = models.ManyToManyField(User, related_name='teams', blank=True)
    description = models.TextField(blank=True)
    logo = models.ImageField(upload_to='team_logos/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name


class Review(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    rating = models.IntegerField(choices=[(i, i) for i in range(1, 6)])
    title = models.CharField(max_length=200)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    helpful_count = models.IntegerField(default=0)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.username} - {self.game.name} ({self.rating}/5)"


class Highlight(models.Model):
    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='highlights')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='highlights')
    title = models.CharField(max_length=200)
    video_url = models.URLField(help_text="YouTube/TikTok/Instagram link")
    description = models.TextField(blank=True)
    likes = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return self.title


# models.py - UPDATED UserProfile
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    bio = models.TextField(max_length=500, blank=True)
    level = models.IntegerField(default=1)
    total_matches = models.IntegerField(default=0)
    win_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    rank = models.IntegerField(null=True, blank=True)
    country = models.CharField(max_length=100, blank=True)
    platform = models.CharField(max_length=100, blank=True)
    play_style = models.CharField(max_length=100, blank=True)

    # Game mode preference
    preferred_mode = models.CharField(
        max_length=20,
        choices=[
            ('CASUAL', 'Casual Play'),
            ('COMPETITIVE', 'Ranked Match'),
            ('TOURNAMENT', 'Tournament'),
            ('PRACTICE', 'Practice/Scrim'),
            ('CUSTOM', 'Custom Game')
        ],
        default='COMPETITIVE',
        blank=True
    )

    date_joined = models.DateTimeField(auto_now_add=True)

    # CHANGED: Remove ManyToMany to Game model, use JSONField instead
    favorite_game_types = models.JSONField(
        default=list,
        blank=True,
        help_text="List of favorite game types from StatSubmission.GAME_CHOICES"
    )

    # Additional fields
    gamer_tag = models.CharField(max_length=100, blank=True)
    main_game = models.CharField(max_length=100, blank=True)
    avatar_color = models.CharField(max_length=7, default='#3b82f6')

    # Privacy settings
    show_online_status = models.BooleanField(default=True)
    show_match_history = models.BooleanField(default=True)
    allow_friend_requests = models.BooleanField(default=True)
    allow_messages = models.BooleanField(default=True)
    profile_visibility = models.CharField(
        max_length=10,
        choices=[
            ('public', 'Public'),
            ('friends', 'Friends Only'),
            ('private', 'Private')
        ],
        default='public'
    )

    # New fields for StatSubmission system
    total_score = models.IntegerField(default=0)
    verified_submissions = models.IntegerField(default=0)
    pending_submissions = models.IntegerField(default=0)
    last_submission = models.DateTimeField(null=True, blank=True)

    def _str_(self):
        return f"{self.user.username}'s Profile"

    # Helper method to get favorite games with details
    @property
    def favorite_games_display(self):
        """Get favorite games with names and icons"""
        from .models import StatSubmission  # Import here to avoid circular import

        favorites = []
        game_choices = dict(StatSubmission.GAME_CHOICES)

        for game_type in self.favorite_game_types:
            game_name = game_choices.get(game_type, game_type)
            # Get icon (first character before space)
            icon = game_name.split(' ')[0] if ' ' in game_name else game_name[0]
            favorites.append({
                'type': game_type,
                'name': game_name,
                'icon': icon,
            })

        return favorites

    # Update stats from StatSubmission
    def update_stats_from_submissions(self):
        """Update profile stats based on StatSubmission data"""
        from django.db.models import Sum, Count

        submissions = self.user.statsubmission_set.all()

        # Get aggregates
        stats = submissions.aggregate(
            total_score=Sum('total_score'),
            verified_count=Count('id', filter=models.Q(status='verified')),
            pending_count=Count('id', filter=models.Q(status='pending')),
            last_submission=Max('created_at'),
        )


        # Update fields
        self.total_score = stats['total_score'] or 0
        self.verified_submissions = stats['verified_count'] or 0
        self.pending_submissions = stats['pending_count'] or 0
        self.last_submission = stats['last_submission']

        # Calculate win rate from submissions
        total_wins = submissions.aggregate(total=Sum('wins'))['total'] or 0
        total_matches = submissions.aggregate(total=Sum('matches_played'))['total'] or 1
        self.win_rate = round((total_wins / total_matches) * 100, 2) if total_matches > 0 else 0

        # Update total matches
        self.total_matches = total_matches

        self.save()



# models.py - LEADERBOARD SECTION

class Leaderboard(models.Model):
    PERIOD_CHOICES = [
        ('DAILY', '📅 Daily'),
        ('WEEKLY', '📆 Weekly'),
        ('MONTHLY', '📊 Monthly'),
        ('ALL_TIME', '🏆 All Time'),
    ]

    game = models.ForeignKey(Game, on_delete=models.CASCADE, related_name='leaderboards')
    period = models.CharField(max_length=20, choices=PERIOD_CHOICES)
    start_date = models.DateTimeField(auto_now_add=True)
    end_date = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ['game', 'period']

    def _str_(self):
        return f"{self.game.name} - {self.get_period_display()}"

    def get_entry_count(self):
        """Safe method to get entry count"""
        return self.entries.count()

    def get_top_entries(self, limit=5):
        """Get top entries for this leaderboard"""
        return self.entries.all().order_by('-total_score', 'rank')[:limit]

    def update_rankings(self):
        """Update ranks for all entries"""
        # Get all entries ordered by total_score (descending)
        entries = self.entries.all().order_by('-total_score')

        # Update ranks
        for rank, entry in enumerate(entries, start=1):
            entry.rank = rank
            entry.save(update_fields=['rank'])

class LeaderboardEntry(models.Model):
    GAME_CHOICES = [
        ('clash_of_clans', '🏰 Clash of Clans'),
        ('asphalt_9', '🏎 Asphalt 9'),
        ('fifa_mobile', '⚽ FIFA Mobile'),
        ('mobile_legends', '⚔ Mobile Legends'),
        ('pubg_mobile', '🔫 PUBG Mobile'),
        ('dream_league_soccer', '🥅 Dream League Soccer'),
        ('efootball', '🎮 eFootball'),
        ('call_of_duty', '🎯 Call of Duty'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE)
    game_type = models.CharField(max_length=50, choices=GAME_CHOICES)
    stats = models.JSONField(default=dict)  # Store ALL game stats here
    total_score = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-total_score', '-updated_at']


    def get_stat(self, key, default=0):
        """Safe way to get a stat value"""
        return self.stats.get(str(key), default)

    def update_stat(self, key, value):
        """Update a single stat and recalculate score"""
        self.stats[str(key)] = value
        self.calculate_score()

    def calculate_score(self):
        """Calculate total_score based on game type"""
        if self.game_type == 'clash_of_clans':
            trophies = self.get_stat('trophies')
            town_hall = self.get_stat('town_hall', 1)
            clan_rank = self.get_stat('clan_rank', 10)
            self.total_score = (trophies * 2) + (town_hall * 1000) + ((11 - clan_rank) * 100)

        elif self.game_type == 'asphalt_9':
            races_won = self.get_stat('races_won')
            best_time = self.get_stat('best_time', 999)
            car_level = self.get_stat('car_level', 1)
            self.total_score = (races_won * 200) - best_time + (car_level * 50)

        elif self.game_type == 'fifa_mobile':
            goals = self.get_stat('goals')
            wins = self.get_stat('wins')
            skill_moves = self.get_stat('skill_moves', 0)
            self.total_score = (goals * 10) + (wins * 150) + (skill_moves * 5)

        elif self.game_type == 'mobile_legends':
            kills = self.get_stat('kills')
            assists = self.get_stat('assists')
            wins = self.get_stat('wins')
            deaths = self.get_stat('deaths', 1)
            kd_ratio = (kills + assists) / deaths if deaths > 0 else kills + assists
            self.stats['kd_ratio'] = round(kd_ratio, 2)
            self.total_score = (kills * 5) + (assists * 3) + (wins * 200)

        elif self.game_type == 'pubg_mobile':
            kills = self.get_stat('kills')
            wins = self.get_stat('wins')
            chicken_dinners = self.get_stat('chicken_dinners', 0)
            survival_time = self.get_stat('survival_time', 0)
            self.total_score = (kills * 15) + (wins * 100) + (chicken_dinners * 500) + (survival_time * 2)

        elif self.game_type == 'dream_league_soccer':
            goals = self.get_stat('goals')
            assists = self.get_stat('assists')
            clean_sheets = self.get_stat('clean_sheets', 0)
            wins = self.get_stat('wins')
            self.total_score = (goals * 20) + (assists * 10) + (clean_sheets * 50) + (wins * 150)

        elif self.game_type == 'efootball':
            goals = self.get_stat('goals')
            pass_accuracy = self.get_stat('pass_accuracy', 0)
            possession = self.get_stat('possession', 50)
            wins = self.get_stat('wins')
            self.total_score = (goals * 15) + (pass_accuracy * 2) + (possession) + (wins * 200)

        elif self.game_type == 'call_of_duty':
            kills = self.get_stat('kills')
            objective_score = self.get_stat('objective_score', 0)
            win_streak = self.get_stat('win_streak', 0)
            wins = self.get_stat('wins')
            self.total_score = (kills * 10) + (objective_score * 5) + (win_streak * 100) + (wins * 150)

        # Save win rate for all games
        matches_played = self.get_stat('matches_played', 1)
        wins = self.get_stat('wins', 0)
        self.stats['win_rate'] = round((wins / matches_played) * 100, 2) if matches_played > 0 else 0

        self.save()

    def _str_(self):
        return f"{self.user.username} - {self.get_game_type_display()} ({self.total_score})"



class StatSubmission(models.Model):
    """Model for game stat submissions with admin verification"""

    GAME_CHOICES = [
        ('fifa_mobile', '⚽ FIFA Mobile'),
        ('pubg_mobile', '🔫 PUBG Mobile'),
        ('clash_of_clans', '🏰 Clash of Clans'),
        ('asphalt_9', '🏎 Asphalt 9'),
        ('mobile_legends', '⚔ Mobile Legends'),
        ('dream_league_soccer', '🥅 Dream League Soccer'),
        ('efootball', '🎮 eFootball'),
        ('call_of_duty', '🎯 Call of Duty'),
    ]

    # ===== PLAYER & GAME INFO =====
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    game_type = models.CharField(max_length=50, choices=GAME_CHOICES)

    # ===== BASIC STATS =====
    wins = models.IntegerField(default=0)
    matches_played = models.IntegerField(default=0)

    # ===== GAME-SPECIFIC STATS =====
    goals = models.IntegerField(default=0, null=True, blank=True)
    kills = models.IntegerField(default=0, null=True, blank=True)
    assists = models.IntegerField(default=0, null=True, blank=True)
    deaths = models.IntegerField(default=0, null=True, blank=True)
    trophies = models.IntegerField(default=0, null=True, blank=True)
    town_hall_level = models.IntegerField(default=1, null=True, blank=True)

    # ===== MEDIA & DESCRIPTION =====
    screenshot = models.ImageField(
        upload_to='stat_screenshots/%Y/%m/%d/',
        blank=True,
        null=True,
        help_text="Upload screenshot as proof of your stats"
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Optional notes about your submission"
    )

    # ===== SCORES =====
    total_score = models.IntegerField(default=0)

    # ===== DATES =====
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # ===== VERIFICATION SYSTEM =====
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', '⏳ Pending Review'),
            ('verified', '✅ Verified'),
            ('rejected', '❌ Rejected'),
            ('flagged', '🚩 Flagged for Review'),
        ],
        default='pending'
    )

    verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_submissions',
        help_text="Admin who verified this submission"
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    rejection_reason = models.TextField(
        blank=True,
        null=True,
        help_text="If rejected, explain why"
    )

    class Meta:
        ordering = ['-total_score']

    # ===== HELPER METHODS =====

    def calculate_score(self):
        """Calculate score based on game type"""
        if self.game_type == 'fifa_mobile':
            self.total_score = (self.goals * 10) + (self.wins * 100)
        elif self.game_type == 'pubg_mobile':
            kd = self.kills / max(self.deaths, 1) if self.deaths > 0 else self.kills
            self.total_score = (self.kills * 10) + (self.wins * 150) + int(kd * 50)
        elif self.game_type == 'clash_of_clans':
            self.total_score = (self.trophies * 2) + (self.town_hall_level * 1000)
        else:
            self.total_score = self.wins * 100

        self.save()

    def verify(self, admin_user):
        """Mark as verified by admin"""
        self.verified = True
        self.status = 'verified'
        self.verified_by = admin_user
        self.verified_at = timezone.now()
        self.save()

    def reject(self, admin_user, reason=""):
        """Mark as rejected by admin"""
        self.verified = False
        self.status = 'rejected'
        self.verified_by = admin_user
        self.verified_at = timezone.now()
        self.rejection_reason = reason
        self.save()

    # ===== PROPERTIES FOR TEMPLATES =====

    @property
    def is_verified(self):
        return self.verified and self.status == 'verified'

    @property
    def is_pending(self):
        return self.status == 'pending'

    @property
    def is_rejected(self):
        return self.status == 'rejected'

    @property
    def win_rate(self):
        if self.matches_played > 0:
            return round((self.wins / self.matches_played) * 100, 2)
        return 0

    def get_stat(self, stat_name, default=0):
        """Get any stat from the model"""
        return getattr(self, stat_name, default)

    def _str_(self):
        return f"{self.user.username} - {self.get_game_type_display()} ({self.total_score})"
    