from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator

class Game(models.Model):
    """Game model to represent different games"""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Emoji or icon for the game")
    banner_image = models.ImageField(upload_to='game_banners/%Y/%m/%d/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # Game-specific fields
    min_players = models.PositiveIntegerField(default=1)
    max_players = models.PositiveIntegerField(default=10)
    platforms = models.CharField(max_length=200, blank=True, help_text="e.g., PC, Mobile, Console")

    class Meta:
        ordering = ['name']

    def __str__(self):
        return f"{self.icon} {self.name}" if self.icon else self.name


# tournament/models.py
class Tournament(models.Model):
    STATUS_CHOICES = [
        ('upcoming', '⏳ Upcoming'),
        ('ongoing', '▶️ Ongoing'),
        ('completed', '✅ Completed'),
        ('cancelled', '❌ Cancelled'),
    ]

    FORMAT_CHOICES = [
        ('single_elimination', 'Single Elimination'),
        ('double_elimination', 'Double Elimination'),
        ('round_robin', 'Round Robin'),
        ('swiss', 'Swiss System'),
        ('free_for_all', 'Free for All'),
    ]

    CURRENCY_CHOICES = [
        ('USD', 'US Dollar ($)'),
        ('EUR', 'Euro (€)'),
        ('GBP', 'British Pound (£)'),
        ('NGN', 'Nigerian Naira (₦)'),
        ('GHS', 'Ghanaian Cedi (₵)'),
        ('KES', 'Kenyan Shilling (KSh)'),
    ]

    # Basic Information
    title = models.CharField(max_length=200)
    description = models.TextField()
    banner_image = models.ImageField(upload_to='tournament_banners/%Y/%m/%d/', blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='upcoming')

    # Link to Game
    game = models.ForeignKey(
        Game,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='tournaments'
    )

    # Tournament Details
    format = models.CharField(max_length=50, choices=FORMAT_CHOICES, default='single_elimination')
    max_participants = models.PositiveIntegerField(default=16)
    current_participants = models.PositiveIntegerField(default=0)

    # Schedule
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    registration_deadline = models.DateTimeField()

    # Financials
    entry_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    game_prize = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    currency = models.CharField(max_length=10, choices=CURRENCY_CHOICES, default='USD')

    # Rules & Requirements
    rules = models.TextField(blank=True)
    requirements = models.TextField(blank=True, help_text="System requirements, rank requirements, etc.")

    # Streaming & Social
    stream_url = models.URLField(blank=True)
    social_media_links = models.JSONField(default=dict, blank=True)

    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_tournaments')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']

    def __str__(self):
        if self.game:
            return f"{self.game.name}: {self.title}"
        return self.title

    def is_registration_open(self):
        """Check if registration is currently open"""
        from django.utils import timezone
        now = timezone.now()

        print(f"DEBUG is_registration_open:")
        print(f"  Status: {self.status}")
        print(f"  Now: {now}")
        print(f"  Start date: {self.start_date}")
        print(f"  Current participants: {self.current_participants}/{self.max_participants}")

        # Check conditions
        is_upcoming = self.status == 'upcoming'
        not_started = now < self.start_date
        not_full = self.current_participants < self.max_participants

        print(f"  Is upcoming: {is_upcoming}")
        print(f"  Not started: {not_started}")
        print(f"  Not full: {not_full}")
        print(f"  Result: {is_upcoming and not_started and not_full}")

        return is_upcoming and not_started and not_full

    def available_slots(self):
        return max(0, self.max_participants - self.current_participants)

    def is_full(self):
        return self.current_participants >= self.max_participants

# In tournament/models.py, after the Tournament class
class TournamentSubscription(models.Model):
    PAYMENT_STATUS = [
        ('pending', '⏳ Pending'),
        ('processing', '🔄 Processing'),
        ('completed', '✅ Completed'),
        ('failed', '❌ Failed'),
        ('refunded', '↩️ Refunded'),
    ]

    PAYMENT_METHODS = [
        ('bank_transfer', '🏦 Bank Transfer'),
        ('mobile_money', '📱 Mobile Money'),
        ('crypto', '₿ Cryptocurrency'),
        ('cash', '💵 Cash'),
        ('other', '📝 Other'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tournament_subscriptions')
    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='subscriptions')
    subscription_date = models.DateTimeField(auto_now_add=True)

    # Payment Information
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHODS, default='mobile_money')
    transaction_id = models.CharField(max_length=100, blank=True, null=True)
    payment_amount = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(0.00)]
    )
    payment_date = models.DateTimeField(null=True, blank=True)

    # Payment Proof
    payment_proof = models.FileField(upload_to='payment_proofs/%Y/%m/%d/', blank=True, null=True)
    payer_name = models.CharField(max_length=255, blank=True, null=True)
    payer_email = models.EmailField(blank=True, null=True)
    payer_phone = models.CharField(max_length=20, blank=True, null=True)

    # Admin Fields
    admin_notes = models.TextField(blank=True, null=True)
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='verified_payments')
    verified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = ['user', 'tournament']
        ordering = ['-subscription_date']

    def __str__(self):
        return f"{self.user.username} - {self.tournament.title} (${self.payment_amount})"

    def is_paid(self):
        return self.payment_status == 'completed'

    def get_payment_proof_url(self):
        if self.payment_proof and hasattr(self.payment_proof, 'url'):
            return self.payment_proof.url
        return None

    def verify_payment(self, admin_user, notes=''):
        """Mark payment as verified"""
        from django.utils import timezone
        self.payment_status = 'completed'
        self.verified_by = admin_user
        self.verified_at = timezone.now()
        if notes:
            self.admin_notes = notes
        self.save()

        # Update tournament participant count
        if self.tournament.current_participants < self.tournament.max_participants:
            self.tournament.current_participants += 1
            self.tournament.save()

        return True


# tournament/models.py - Make sure these classes exist

class Match(models.Model):
    """Individual match within a tournament"""
    MATCH_STATUS = [
        ('scheduled', '⏰ Scheduled'),
        ('ongoing', '▶️ Ongoing'),
        ('completed', '✅ Completed'),
        ('cancelled', '❌ Cancelled'),
    ]

    tournament = models.ForeignKey(Tournament, on_delete=models.CASCADE, related_name='matches')
    round_number = models.PositiveIntegerField(default=1)
    match_number = models.PositiveIntegerField()

    # Players/teams in the match
    player1 = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='matches_as_player1')
    player2 = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                related_name='matches_as_player2')

    # Match details
    scheduled_time = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=MATCH_STATUS, default='scheduled')
    score_player1 = models.IntegerField(default=0)
    score_player2 = models.IntegerField(default=0)

    # Winner
    winner = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='matches_won')

    class Meta:
        ordering = ['round_number', 'match_number']
        unique_together = ['tournament', 'round_number', 'match_number']

    def __str__(self):
        return f"Match {self.match_number} - Round {self.round_number} - {self.tournament.title}"


class TournamentResult(models.Model):
    """Final results/standings for a tournament"""
    tournament = models.OneToOneField(Tournament, on_delete=models.CASCADE, related_name='final_result')

    # Winners
    first_place = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='first_place_wins')
    second_place = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='second_place_wins')
    third_place = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='third_place_wins')

    # Final scores/stats
    final_standings = models.JSONField(default=list, blank=True)  # List of user standings
    completed_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Results for {self.tournament.title}"