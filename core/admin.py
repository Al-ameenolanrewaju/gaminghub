from django.contrib import admin
from .models import Game, Room, Review, Highlight, Team, UserProfile
from django.utils.html import format_html
from .models import StatSubmission



@admin.register(Game)
class GameAdmin(admin.ModelAdmin):
    list_display = ('name', 'genre', 'platform', 'is_featured', 'created_at')
    list_filter = ('genre', 'platform', 'is_featured')
    search_fields = ('name', 'description', 'developer')





@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    # FIXED: Use fields that actually exist in your Room model
    list_display = ('title', 'room_code', 'game', 'host', 'is_active', 'created_at')
    list_filter = ('is_active', 'game', 'status')  # Use 'status' not 'privacy' or 'game_mode'
    search_fields = ('title', 'room_code', 'host__username', 'description')
    readonly_fields = ('room_code', 'created_at')

    # Optional: Show players in admin
    filter_horizontal = ('players',)

    fieldsets = (
        ('Room Details', {
            'fields': ('title', 'room_code', 'description', 'game')
        }),
        ('Players', {
            'fields': ('host', 'players', 'max_players')
        }),
        ('Status', {
            'fields': ('is_active', 'status', 'game_password')
        }),
        ('Timestamps', {
            'fields': ('created_at',),
            'classes': ('collapse',)
        }),
    )












@admin.register(StatSubmission)
class StatSubmissionAdmin(admin.ModelAdmin):
    # === LIST DISPLAY ===
    list_display = [
        'user',
        'game_type_display',
        'wins',
        'total_score',
        'status_badge',
        'verified_badge',
        'verified_at_short',
        'screenshot_link',
        'actions_column',
    ]

    list_display_links = ['user', 'game_type_display']

    # === FILTERS ===
    list_filter = [
        'status',
        'verified',
        'game_type',
        'verified_at',
        'created_at',
    ]

    # === SEARCH ===
    search_fields = ['user__username', 'description', 'rejection_reason']

    # === READONLY FIELDS ===
    readonly_fields = [
        'created_at',
        'updated_at',
        'total_score',
        'screenshot_preview',
        'verification_info',
    ]

    # === FIELDSETS ===
    fieldsets = (
        ('Player & Game', {
            'fields': ('user', 'game_type', 'description')
        }),
        ('Game Statistics', {
            'fields': (
                ('wins', 'matches_played'),
                ('goals', 'assists'),
                ('kills', 'deaths'),
                ('trophies', 'town_hall_level'),
            ),
            'classes': ('collapse',),
        }),
        ('Media Proof', {
            'fields': ('screenshot', 'screenshot_preview'),
        }),
        ('Verification Status', {
            'fields': (
                'status',
                'verified',
                'rejection_reason',
                'verification_info',
            ),
        }),
        ('Scores & Dates', {
            'fields': ('total_score', ('created_at', 'updated_at')),
            'classes': ('collapse',),
        }),
    )

    # === ACTIONS ===
    actions = [
        'verify_selected',
        'reject_selected',
        'mark_as_pending',
        'flag_for_review',
        'recalculate_scores',
        'delete_selected',
    ]

    # === CUSTOM METHODS ===

    # Display methods
    def game_type_display(self, obj):
        return obj.get_game_type_display()

    game_type_display.short_description = 'Game'
    game_type_display.admin_order_field = 'game_type'

    def status_badge(self, obj):
        colors = {
            'pending': 'warning',
            'verified': 'success',
            'rejected': 'danger',
            'flagged': 'info',
        }
        icons = {
            'pending': '⏳',
            'verified': '✅',
            'rejected': '❌',
            'flagged': '🚩',
        }
        color = colors.get(obj.status, 'secondary')
        icon = icons.get(obj.status, '❓')

        return format_html(
            '<span class="badge bg-{}">{}{}</span>',
            color,
            icon,
            obj.get_status_display()
        )

    status_badge.short_description = 'Status'

    def verified_badge(self, obj):
        # FIXED: Proper format_html usage with arguments
        if obj.status == 'verified':
            return format_html(
                '<span style="background-color: green; color: white; padding: 2px 8px; border-radius: 10px;">{}</span>',
                obj.get_status_display()
            )
        elif obj.status == 'pending':
            return format_html(
                '<span style="background-color: orange; color: white; padding: 2px 8px; border-radius: 10px;">{}</span>',
                obj.get_status_display()
            )
        else:
            return format_html(
                '<span style="background-color: red; color: white; padding: 2px 8px; border-radius: 10px;">{}</span>',
                obj.get_status_display()
            )

    def verified_at_short(self, obj):
        if obj.verified_at:
            return obj.verified_at.strftime('%b %d, %H:%M')
        return '-'

    verified_at_short.short_description = 'Verified At'

    def screenshot_link(self, obj):
        if obj.screenshot:
            return format_html(
                '<a href="{}" target="_blank" style="color: #0d6efd;">📸 View</a>',
                obj.screenshot.url
            )
        return format_html('<span style="color: #6c757d;">📷 No image</span>')

    screenshot_link.short_description = 'Screenshot'

    def actions_column(self, obj):
        return format_html(
            '<div style="white-space: nowrap;">'
            '<a href="{}" class="btn btn-success btn-sm" style="margin-right: 5px;">✓</a>'
            '<a href="{}" class="btn btn-danger btn-sm">🗑</a>'
            '</div>',
            f'{obj.id}/verify/',
            f'{obj.id}/delete/'
        )

    actions_column.short_description = 'Actions'

    # Detail view methods
    def screenshot_preview(self, obj):
        if obj.screenshot:
            return format_html(
                '<img src="{}" style="max-width: 300px; max-height: 300px; '
                'border: 2px solid #ddd; border-radius: 5px;" />',
                obj.screenshot.url
            )
        return 'No screenshot uploaded'

    screenshot_preview.short_description = 'Screenshot Preview'

    def verification_info(self, obj):
        if obj.verified_by and obj.verified_at:
            return format_html(
                '<div style="background: #d1e7dd; padding: 10px; border-radius: 5px;">'
                '<strong>Verified by:</strong> {}<br>'
                '<strong>Verified at:</strong> {}'
                '</div>',
                obj.verified_by.username,
                obj.verified_at.strftime('%Y-%m-%d %H:%M:%S')
            )
        elif obj.status == 'rejected' and obj.rejection_reason:
            return format_html(
                '<div style="background: #f8d7da; padding: 10px; border-radius: 5px;">'
                '<strong>Rejection Reason:</strong><br>{}'
                '</div>',
                obj.rejection_reason
            )
        return 'Awaiting verification'

    verification_info.short_description = 'Verification Details'

    # === CUSTOM ACTIONS ===

    def verify_selected(self, request, queryset):
        count = 0
        for submission in queryset:
            submission.verify(request.user)
            count += 1
        self.message_user(request, f'✅ Verified {count} submission(s).')

    verify_selected.short_description = "✅ Verify selected"

    def reject_selected(self, request, queryset):
        count = 0
        for submission in queryset:
            submission.reject(request.user, "Rejected via admin action")
            count += 1
        self.message_user(request, f'❌ Rejected {count} submission(s).')

    reject_selected.short_description = "❌ Reject selected"

    def mark_as_pending(self, request, queryset):
        updated = queryset.update(status='pending', verified=False)
        self.message_user(request, f'⏳ Marked {updated} submission(s) as pending.')

    mark_as_pending.short_description = "⏳ Mark as pending"

    def flag_for_review(self, request, queryset):
        updated = queryset.update(status='flagged')
        self.message_user(request, f'🚩 Flagged {updated} submission(s) for review.')

    flag_for_review.short_description = "🚩 Flag for review"

    def recalculate_scores(self, request, queryset):
        count = 0
        for submission in queryset:
            submission.calculate_score()
            count += 1
        self.message_user(request, f'🔢 Recalculated scores for {count} submission(s).')

    recalculate_scores.short_description = "🔢 Recalculate scores"

    # === ADMIN CSS ===
    class Media:
        css = {
            'all': ('admin/css/admin_custom.css',)
        }


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'game', 'leader', 'created_at')
    search_fields = ('name', 'description')



@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'level', 'total_matches', 'win_rate', 'platform')
    list_filter = ('platform', 'play_style')
    search_fields = ('user__username', 'bio')



