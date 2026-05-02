# clashroyale/views.py
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from .models import ClashRoyalePlayer
import requests
from datetime import datetime, timedelta
from .utils.clash_api import fetch_player_data  # Import the helper


# SET THIS TO False WHEN YOU GET REAL API WORKING
USE_MOCK_DATA = True


def clash_royale_leaderboard(request):
    """Main leaderboard page"""
    players = ClashRoyalePlayer.objects.all().order_by('-trophies')

    # Add ranks and prepare data
    ranked_players = []
    for index, player in enumerate(players[:100], 1):  # Top 100
        ranked_players.append({
            'rank': index,
            'player': player,
            'trophies': player.trophies,
            'win_rate': f"{player.win_rate:.1f}%",
            'is_mock': player.is_mock,
            'is_current_user': player.user == request.user,
        })

    # Get user's rank if authenticated
    user_rank = None
    if request.user.is_authenticated:
        user_player = ClashRoyalePlayer.objects.filter(user=request.user).first()
        if user_player:
            # Count players with higher trophies + 1
            user_rank = ClashRoyalePlayer.objects.filter(
                trophies__gt=user_player.trophies
            ).count() + 1

    context = {
        'players': ranked_players,
        'total_players': players.count(),
        'top_trophies': players.first().trophies if players else 0,
        'top_player': players.first(),
        'last_updated': players.first().last_updated if players else None,
        'user_rank': user_rank,
        'has_clash_royale': ClashRoyalePlayer.objects.filter(
            user=request.user).exists() if request.user.is_authenticated else False,
        'use_mock_data': USE_MOCK_DATA,
    }

    return render(request, 'clashroyale/leaderboard.html', context)


@login_required
def connect_account(request):
    """Connect Clash Royale account"""
    if request.method == 'POST':
        player_tag = request.POST.get('player_tag', '').strip().upper()

        # Validate tag format
        if not player_tag.startswith('#'):
            player_tag = '#' + player_tag

        if len(player_tag) < 4 or len(player_tag) > 20:
            messages.error(request, "Invalid Player Tag length")
            return redirect('connect_clash_royale')

        # Check if tag already exists
        if ClashRoyalePlayer.objects.filter(player_tag=player_tag).exists():
            messages.error(request, "This Player Tag is already connected")
            return redirect('connect_clash_royale')

        # Check if user already has account
        if ClashRoyalePlayer.objects.filter(user=request.user).exists():
            messages.warning(request, "You already have a connected account")
            return redirect('clash_royale_leaderboard')

        if USE_MOCK_DATA:
            # Use mock data
            mock_data = ClashRoyalePlayer.generate_mock_data(player_tag)

            player = ClashRoyalePlayer.objects.create(
                user=request.user,
                player_tag=player_tag,
                **{k: v for k, v in mock_data.items() if k != 'is_mock'}
            )
            player.is_mock = True
            player.save()

            messages.success(request, f"✅ Connected {mock_data['player_name']}! (Mock Data)")
            return redirect('clash_royale_leaderboard')

        else:
            # REAL API CODE (for when you get it working)
            api_key = settings.CLASH_ROYALE_API_KEY
            clean_tag = player_tag.replace('#', '')

            url = f"https://api.clashroyale.com/v1/players/%23{clean_tag}"
            headers = {"Authorization": f"Bearer {api_key}"}

            try:
                response = requests.get(url, headers=headers, timeout=10)

                if response.status_code == 200:
                    data = response.json()

                    player = ClashRoyalePlayer.objects.create(
                        user=request.user,
                        player_tag=player_tag,
                        player_name=data.get('name', 'Unknown'),
                        trophies=data.get('trophies', 0),
                        best_trophies=data.get('bestTrophies', 0),
                        level=data.get('expLevel', 1),
                        wins=data.get('wins', 0),
                        losses=data.get('losses', 0),
                        draws=data.get('draws', 0),
                        total_battles=data.get('battleCount', 0),
                        clan_name=data.get('clan', {}).get('name', ''),
                        clan_tag=data.get('clan', {}).get('tag', ''),
                        is_mock=False,
                    )
                    player.update_win_rate()

                    messages.success(request, "Account connected successfully!")
                    return redirect('clash_royale_leaderboard')

                else:
                    messages.error(request, f"API Error: {response.status_code}")

            except Exception as e:
                messages.error(request, f"Connection failed: {str(e)}")

    return render(request, 'clashroyale/connect.html', {'use_mock_data': USE_MOCK_DATA})




@login_required
def refresh_stats(request):
    """Refresh player stats from Clash Royale API"""
    # Note: Changed from .first() since you might have multiple players per user
    try:
        player = ClashRoyalePlayer.objects.get(user=request.user, player_tag=request.GET.get('player_tag', ''))
    except ClashRoyalePlayer.DoesNotExist:
        # Get first player for the user
        player = ClashRoyalePlayer.objects.filter(user=request.user).first()

    if not player:
        messages.error(request, "No Clash Royale account connected")
        return redirect('clash_royale_leaderboard')

    if settings.USE_MOCK_DATA or player.is_mock:
        # Update mock data with slight changes
        import random
        random.seed(hash(player.player_tag) + hash(datetime.now().timestamp()))

        change = random.randint(-50, 100)
        player.trophies = max(0, player.trophies + change)
        player.best_trophies = max(player.best_trophies, player.trophies)

        player.wins += random.randint(0, 10)
        player.losses += random.randint(0, 5)
        player.draws += random.randint(0, 2)
        player.total_battles = player.wins + player.losses + player.draws

        player.update_win_rate()
        player.save()

        messages.success(request,
                         f"Mock stats updated! Trophies: {player.trophies} (▲{change if change > 0 else change})")
    else:
        # Real API refresh code
        try:
            # Fetch fresh data from API
            api_data = fetch_player_data(player.player_tag)

            # Update player model with API data
            old_trophies = player.trophies

            player.player_name = api_data.get('name', player.player_name)
            player.trophies = api_data.get('trophies', 0)
            player.best_trophies = api_data.get('bestTrophies', player.best_trophies)
            player.level = api_data.get('expLevel', player.level)

            # Battle stats
            player.wins = api_data.get('wins', 0)
            player.losses = api_data.get('losses', 0)
            player.draws = api_data.get('draws', 0)
            player.total_battles = api_data.get('battleCount', 0)

            # Update win rate
            player.update_win_rate()

            # Clan info
            clan_data = api_data.get('clan', {})
            if clan_data:
                player.clan_name = clan_data.get('name', '')
                player.clan_tag = clan_data.get('tag', '')

            # Mark as real data
            player.is_mock = False
            player.save()

            # Calculate trophy change
            trophy_change = player.trophies - old_trophies
            if trophy_change > 0:
                change_symbol = f"▲{trophy_change}"
            elif trophy_change < 0:
                change_symbol = f"▼{abs(trophy_change)}"
            else:
                change_symbol = "0"

            messages.success(
                request,
                f"Stats refreshed from API! Trophies: {player.trophies} ({change_symbol})"
            )

        except Exception as e:
            messages.error(
                request,
                f"Failed to refresh stats: {str(e)}"
            )
            # Log error but don't crash
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Clash Royale API error for user {request.user}: {str(e)}")

    return redirect('clash_royale_leaderboard')


def about_clash_royale(request):
    """Information page about Clash Royale integration"""
    return render(request, 'clashroyale/about.html', {
        'use_mock_data': USE_MOCK_DATA,
        'total_players': ClashRoyalePlayer.objects.count(),
    })



def toggle_data_source(request):
    """Toggle between mock and real data for current user"""
    if not request.user.is_authenticated:
        messages.error(request, "Please log in first")
        return redirect('login')

    player = ClashRoyalePlayer.objects.filter(user=request.user).first()

    if not player:
        messages.error(request, "No player found")
        return redirect('clash_royale_leaderboard')

    if player.is_mock:
        # Switch to real data
        if not settings.CLASH_ROYALE_API_KEY:
            messages.error(request, "API key not configured. Contact administrator.")
        else:
            player.is_mock = False
            player.save()
            messages.success(request, "Switched to REAL API data. Click 'Refresh Stats' to update.")
    else:
        # Switch to mock data
        player.is_mock = True
        player.save()
        messages.success(request, "Switched to MOCK data")

    return redirect('clash_royale_leaderboard')