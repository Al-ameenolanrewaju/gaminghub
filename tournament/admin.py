## tournament/admin.py - WORKING VERSION
from django.contrib import admin
from django.utils.html import format_html
from .models import Game, Tournament, Match,TournamentSubscription, TournamentResult

# Tournament Admin - Simple

@admin.register(TournamentSubscription)
class TournamentSubscriptionAdmin(admin.ModelAdmin):
    # MINIMAL VERSION - no custom methods
    list_display = [
        'id',  # Add id for debugging
        'user',
        'tournament',
        'payment_status',
        'payment_method',
    ]
    list_display = [
        'id',
        'user',
        'tournament',
        'payment_status_display',  # Use custom method
        'payment_method',
    ]

    list_filter = ['payment_status']
    search_fields = ['user__username']

    def payment_status_display(self, obj):
        # SIMPLE VERSION - no format_html yet
        return obj.get_payment_status_display()  # Plain text

    payment_status_display.short_description = 'Status'

    list_filter = ['payment_status']
    search_fields = ['user__username']

    def payment_status_display(self, obj):
        status = obj.get_payment_status_display()
        # Simple format_html with ONE placeholder
        return format_html(
            '<strong>{}</strong>',
            status
        )

    def payment_status_display(self, obj):
        colors = {
            'pending': 'orange',
            'processing': 'blue',
            'completed': 'green',
            'failed': 'red',
            'refunded': 'gray',
        }
        color = colors.get(obj.payment_status, 'gray')
        status_display = obj.get_payment_status_display()

        # DEBUG: Print to console to see what's happening
        print(f"DEBUG: status={obj.payment_status}, display={status_display}, color={color}")

        return format_html(
            '<span style="background:{};color:white;padding:3px 6px;border-radius:3px;">{}</span>',
            color,
            status_display
        )
    # NO list_editable for now
    # NO custom methods for now


# In tournament/admin.py



@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ['name', 'icon', 'is_active', 'created_at', 'tournament_count']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'description']
    list_editable = ['is_active']

    fieldsets = (
        ('Basic Info', {
            'fields': ('name', 'icon', 'description', 'is_active')
        }),
        ('Game Details', {
            'fields': ('min_players', 'max_players', 'platforms')
        }),
        ('Media', {
            'fields': ('banner_image',),
            'classes': ('collapse',)
        }),
    )

    def tournament_count(self, obj):
        return obj.tournaments.count()

    tournament_count.short_description = '# Tournaments'


# Update your TournamentAdmin to include game field
@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = ['title', 'game', 'status', 'start_date', 'game_prize', 'current_participants']
    list_filter = ['status', 'game', 'start_date']
    search_fields = ['title', 'description']
    list_editable = ['status']

    # Add 'game' to your fieldsets
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'game', 'description', 'banner_image', 'status')
        }),
        ('Tournament Details', {
            'fields': ('format', 'max_participants', 'current_participants')
        }),
        ('Schedule', {
            'fields': ('start_date', 'end_date', 'registration_deadline')
        }),
        ('Financials', {
            'fields': ('entry_fee', 'game_prize', 'currency')
        }),
        ('Rules & Requirements', {
            'fields': ('rules', 'requirements'),
            'classes': ('collapse',)
        }),
        ('Streaming & Social', {
            'fields': ('stream_url', 'social_media_links'),
            'classes': ('collapse',)
        }),
    )

    # Add autocomplete for game field if you have many games
    autocomplete_fields = ['game']
@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ['tournament', 'round_number', 'match_number', 'score_player1', 'score_player2','player1', 'player2', 'winner', 'status']
    list_filter = ['tournament', 'status', 'round_number']
    search_fields = ['tournament__title', 'player1__username', 'player2__username']
    list_editable = ['status', 'score_player1', 'score_player2', 'winner']

@admin.register(TournamentResult)
class TournamentResultAdmin(admin.ModelAdmin):
    list_display = ['tournament', 'first_place', 'second_place', 'third_place', 'completed_at']
    list_filter = ['completed_at']
    search_fields = ['tournament__title', 'first_place__username', 'second_place__username']
    autocomplete_fields = ['tournament', 'first_place', 'second_place', 'third_place']

# Your existing TournamentSubscriptionAdmin remains