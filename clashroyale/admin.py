from django.contrib import admin

# Register your models here.
# clashroyale/admin.py
from django.contrib import admin
from .models import ClashRoyalePlayer


@admin.register(ClashRoyalePlayer)
class ClashRoyalePlayerAdmin(admin.ModelAdmin):
    list_display = ['player_name', 'player_tag', 'trophies', 'user', 'is_mock', 'last_updated']
    list_filter = ['is_mock', 'clan_name', 'level']
    search_fields = ['player_name', 'player_tag', 'user__username']
    ordering = ['-trophies']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')