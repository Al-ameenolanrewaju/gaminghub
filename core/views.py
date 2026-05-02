from django.contrib.auth import login
from django.contrib.auth.forms import UserCreationForm
from .models import Game, User
from django.shortcuts import render, redirect, get_object_or_404
from .forms import CreateRoomForm
from .models import Room
from django.http import Http404
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail, BadHeaderError
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.contrib import messages
from .forms import ContactForm
from django.views.decorators.csrf import csrf_exempt






# views.py - Add this at the top after imports
GAME_TYPE_CONFIGS = {
    # FPS/Battle Games
    'FPS': {
        'form_fields': ['kills', 'deaths', 'wins', 'matches_played'],
        'field_labels': {
            'kills': 'Kills',
            'deaths': 'Deaths',
            'wins': 'Wins',
            'matches_played': 'Matches Played'
        },
        'button_text': 'Submit Battle Stats',
        'icon': '🔫'
    },

    # Racing Games
    'RACING': {
        'form_fields': ['race_time', 'race_position', 'best_lap', 'matches_played'],
        'field_labels': {
            'race_time': 'Race Time (e.g., 1:23.45)',
            'race_position': 'Finishing Position',
            'best_lap': 'Best Lap Time (optional)',
            'matches_played': 'Races Played'
        },
        'button_text': 'Submit Race Time',
        'icon': '🏎'
    },

    # Football/Soccer Games
    'FOOTBALL': {
        'form_fields': ['goals', 'assists', 'clean_sheet', 'matches_played'],
        'field_labels': {
            'goals': 'Goals Scored',
            'assists': 'Assists',
            'clean_sheet': 'Clean Sheet (no goals conceded)',
            'matches_played': 'Matches Played'
        },
        'field_types': {
            'clean_sheet': 'checkbox'
        },
        'button_text': 'Submit Match Stats',
        'icon': '⚽'
    },

    # MOBA Games
    'MOBA': {
        'form_fields': ['kills', 'deaths', 'assists', 'wins', 'matches_played'],
        'field_labels': {
            'kills': 'Kills',
            'deaths': 'Deaths',
            'assists': 'Assists',
            'wins': 'Games Won',
            'matches_played': 'Matches Played'
        },
        'button_text': 'Submit MOBA Stats',
        'icon': '⚔'
    },

    # Battle Royale
    'BATTLE_ROYALE': {
        'form_fields': ['kills', 'placement', 'wins', 'matches_played'],
        'field_labels': {
            'kills': 'Eliminations',
            'placement': 'Final Placement (e.g., 1st, 2nd)',
            'wins': 'Victory Royales',
            'matches_played': 'Matches Played'
        },
        'button_text': 'Submit Battle Royale Stats',
        'icon': '🎯'
    },

    # Strategy Games
    'STRATEGY': {
        'form_fields': ['score', 'wins', 'matches_played'],
        'field_labels': {
            'score': 'Total Score',
            'wins': 'Games Won',
            'matches_played': 'Matches Played'
        },
        'button_text': 'Submit Strategy Stats',
        'icon': '♟'
    },

    # Default for other games
    'DEFAULT': {
        'form_fields': ['score', 'matches_played'],
        'field_labels': {
            'score': 'Your Score',
            'matches_played': 'Games Played'
        },
        'button_text': 'Submit Game Stats',
        'icon': '🎮'
    }
}


def home(request):
    featured_games = Game.objects.filter(is_featured=True)[:6]
    upcoming_rooms = Room.objects.filter(
        is_active=True
    ).order_by('created_at')[:6]

    context = {
        'featured_games': featured_games,
        'upcoming_rooms': upcoming_rooms,
    }
    return render(request, 'core/home.html', context)


# views.py - Add a game list view
def game_list(request):
    """Show all available games"""
    games = []
    for game_id, game_name in LeaderboardEntry.GAME_CHOICES:
        games.append({
            'id': game_id,
            'name': game_name,
            'url': f'/leaderboards/{game_id}/'
        })

    return render(request, 'core/game_list.html', {'games': games})


def game_detail(request, pk):
    game = get_object_or_404(Game, pk=pk)
    reviews = game.reviews.all()[:5]
    rooms = game.rooms.filter(is_active=True).order_by('created_at')[:5]
    highlights = game.highlights.all()[:3]

    context = {
        'game': game,
        'reviews': reviews,
        'rooms': rooms,
        'highlights': highlights,
    }
    return render(request, 'core/game_detail.html', context)


from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth import login
from django.contrib import messages
from django.shortcuts import render, redirect
from .models import UserProfile


def register(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)

        if form.is_valid():
            # Save the user first
            user = form.save()

            # Get email from POST data and update user
            email = request.POST.get('email', '').strip()
            if email:
                user.email = email
                user.save()

            # Create user profile
            UserProfile.objects.create(user=user)

            # Send welcome email
            try:
                send_welcome_email(user, email)
                messages.success(request, 'Account created successfully! Welcome email sent.')
            except Exception as e:
                # Still register even if email fails
                print(f"Email error: {str(e)}")
                messages.success(request, 'Account created successfully! (Email not sent)')

            login(request, user)
            return redirect('home')
    else:
        form = UserCreationForm()

    return render(request, 'core/register.html', {'form': form})


def send_welcome_email(user, email):
    """Send welcome email to new user"""
    subject = f"🎮 Welcome to Gaming Hub!"

    message = f"""
    Hello {user.username}!

    🎉 Welcome to Gaming Hub - Your Ultimate Gaming Destination! 🎉

    We're thrilled to have you join our community of gamers. 
    Get ready to experience:

    🎮 Multiplayer Gaming Rooms
    🏆 Competitive Tournaments  
    💬 Live Chat with Players
    📱 Cross-Platform Play
    🎯 Real-Time Game Stats

    ---

    Your Account Details:
    Username: {user.username}
    Email: {email}

    ---

    Quick Start:
    1. Browse available games
    2. Join or create a game room
    3. Connect with players
    4. Start playing!

    ---

    Need Help?
    • Check our FAQ: http://127.0.0.1:8000/help/
    • Contact Support: support@gaminghub.com
    • Visit Community: http://127.0.0.1:8000/community/

    ---

    Stay Connected:
    • Twitter: @GamingHub
    • Discord: Join our server
    • YouTube: Gaming Hub Official

    ---

    Happy Gaming! 🎮

    Best regards,
    The Gaming Hub Team

    ---

    PS: This is an automated email. Please do not reply directly.
    """

    # HTML version for email clients that support it
    html_message = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <style>
            body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
            .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
            .header {{ background: #4f46e5; color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }}
            .content {{ padding: 30px; background: #f9fafb; }}
            .button {{ 
                display: inline-block; 
                padding: 14px 28px; 
                background: #4f46e5; 
                color: white; 
                text-decoration: none; 
                border-radius: 8px; 
                font-weight: bold;
                margin: 20px 0; 
            }}
            .feature {{ 
                background: white; 
                padding: 15px; 
                border-radius: 8px; 
                margin: 10px 0;
                border-left: 4px solid #4f46e5;
            }}
            .footer {{ 
                margin-top: 30px; 
                padding-top: 20px; 
                border-top: 1px solid #e5e7eb; 
                color: #6b7280; 
                font-size: 14px; 
                text-align: center;
            }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🎮 Welcome to Gaming Hub!</h1>
                <p>Your Ultimate Gaming Destination</p>
            </div>
            <div class="content">
                <h2>Hello {user.username}! 👋</h2>
                <p>We're thrilled to have you join our community of gamers.</p>

                <h3>🚀 Get Started</h3>
                <div class="feature">
                    <strong>🎮 Multiplayer Gaming Rooms</strong>
                    <p>Join thousands of players in real-time games</p>
                </div>
                <div class="feature">
                    <strong>🏆 Competitive Tournaments</strong>
                    <p>Compete for rankings and rewards</p>
                </div>
                <div class="feature">
                    <strong>💬 Live Chat</strong>
                    <p>Connect with players worldwide</p>
                </div>
                <div class="feature">
                    <strong>📱 Cross-Platform Play</strong>
                    <p>Play on any device - PC, Mobile, Tablet</p>
                </div>

                <center>
                    <a href="http://127.0.0.1:8000/games/" class="button">
                        🎯 Start Playing Now →
                    </a>
                </center>

                <h3>📋 Your Account</h3>
                <p><strong>Username:</strong> {user.username}</p>
                <p><strong>Email:</strong> {email}</p>

                <h3>❓ Need Help?</h3>
                <p>• <a href="http://127.0.0.1:8000/help/">Help Center</a></p>
                <p>• Email: support@gaminghub.com</p>
                <p>• <a href="http://127.0.0.1:8000/community/">Community Forum</a></p>

                <h3>🌐 Stay Connected</h3>
                <p>• Twitter: <a href="https://twitter.com/GamingHub">@GamingHub</a></p>
                <p>• Discord: <a href="#">Join our server</a></p>
                <p>• YouTube: Gaming Hub Official</p>

                <p style="margin-top: 30px; text-align: center; font-size: 18px;">
                    <strong>Happy Gaming! 🎮</strong><br>
                    <em>The Gaming Hub Team</em>
                </p>
            </div>
            <div class="footer">
                <p>© 2025 Gaming Hub. All rights reserved.</p>
                <p>This is an automated message. Please do not reply directly to this email.</p>
                <p><small>You're receiving this email because you signed up for Gaming Hub.</small></p>
            </div>
        </div>
    </body>
    </html>
    """

    # Send the email
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        html_message=html_message,
        fail_silently=False,  # Set to True in production to prevent errors
    )



@login_required
def create_room(request):
    """Create a new game room"""
    if request.method == 'POST':
        form = CreateRoomForm(request.POST)
        if form.is_valid():
            room = form.save(commit=False)
            room.host = request.user
            room.save()

            messages.success(request,
                             f'🎮 Room created! Share code: {room.room_code}')
            return redirect('room_detail', room_code=room.room_code)
    else:
        form = CreateRoomForm()

    return render(request, 'core/create_room.html', {'form': form})



def room_list(request):
    rooms = Room.objects.filter(is_active=True).order_by('-created_at')
    for room in rooms:
        room.user_can_join = room.can_user_join(request.user)
    return render(request, 'core/room_list.html', {'rooms': rooms})

def room_detail(request, room_code):
    room = Room.objects.get(room_code=room_code)
    return render(request, 'core/room_detail.html', {'room': room})

def join_room(request, room_code):
    room = Room.objects.get(room_code=room_code)
    if request.user.is_authenticated:
        room.players.add(request.user)
    return redirect('room_detail', room_code=room_code)





@login_required
def leave_room(request, room_code):
    """Leave a room"""
    room = get_object_or_404(Room, room_code=room_code)

    if request.user in room.players.all():
        room.players.remove(request.user)
        messages.success(request, 'Left the room')

    return redirect('room_list')




from .models import Leaderboard, LeaderboardEntry, StatSubmission
from .forms import StatSubmissionForm






from django.contrib.auth.views import PasswordResetView, PasswordResetDoneView, PasswordResetConfirmView, PasswordResetCompleteView
from django.urls import reverse_lazy

class CustomPasswordResetView(PasswordResetView):
    template_name = 'password_reset.html'
    email_template_name = 'password_reset_email.html'
    success_url = reverse_lazy('password_reset_done')

class CustomPasswordResetDoneView(PasswordResetDoneView):
    template_name = 'password_reset_done.html'

class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    template_name = 'password_reset_confirm.html'
    success_url = reverse_lazy('password_reset_complete')

class CustomPasswordResetCompleteView(PasswordResetCompleteView):
    template_name = 'password_reset_complete.html'

def test_template(request):
    return render(request, 'core/password_reset_form.html')


# core/views.py

from .models import UserProfile


def profile_view(request, username):
    # Get the user whose profile we're viewing
    user_profile = get_object_or_404(User, username=username)
    user_profile_obj = UserProfile.objects.get_or_create(user=user_profile)[0]

    # Get user's StatSubmission entries
    submissions = StatSubmission.objects.filter(
        user=user_profile
    ).order_by('-updated_at')

    # Calculate REAL STATISTICS
    from django.db.models import Sum, Count, Max, Min
    from django.db import models

    # First get basic aggregates
    basic_stats = submissions.aggregate(
        total_kills=Sum('kills'),
        total_deaths=Sum('deaths'),
        total_wins=Sum('wins'),
        total_matches_played=Sum('matches_played'),
        total_goals=Sum('goals'),
        total_assists=Sum('assists'),
        total_score_sum=Sum('total_score'),
        best_score=Max('total_score'),
        worst_score=Min('total_score'),
        total_submissions=Count('id'),
        verified_count=Count('id', filter=models.Q(status='verified')),
        pending_count=Count('id', filter=models.Q(status='pending')),
        rejected_count=Count('id', filter=models.Q(status='rejected')),
        games_played=Count('game_type', distinct=True),
    )

    # Calculate averages manually
    total_submissions = basic_stats['total_submissions'] or 1
    avg_wins = (basic_stats['total_wins'] or 0) / total_submissions
    avg_matches = (basic_stats['total_matches_played'] or 0) / total_submissions
    avg_score = (basic_stats['total_score_sum'] or 0) / total_submissions

    # Calculate win rate
    total_wins = basic_stats['total_wins'] or 0
    total_matches = basic_stats['total_matches_played'] or 1
    actual_win_rate = round((total_wins / total_matches) * 100, 1) if total_matches > 0 else 0

    # Calculate K/D ratio
    total_kills = basic_stats['total_kills'] or 0
    total_deaths = basic_stats['total_deaths'] or 1
    overall_kd = round(total_kills / total_deaths, 2) if total_deaths > 0 else total_kills

    # Get RECENT ACTIVITY (last 7 days)
    from datetime import timedelta
    from django.utils import timezone

    week_ago = timezone.now() - timedelta(days=7)
    recent_activity = []

    # Activity 1: Recent submissions
    recent_submissions_activity = submissions.filter(
        created_at__gte=week_ago
    ).order_by('-created_at')[:5]

    for submission in recent_submissions_activity:
        recent_activity.append({
            'type': 'stats_submitted',
            'timestamp': submission.created_at,
            'title': f"Submitted {submission.get_game_type_display()} stats",
            'details': f"Score: {submission.total_score} | Status: {submission.get_status_display()}",
            'icon': '📊'
        })

    # Activity 2: Recent verifications
    recent_verifications = submissions.filter(
        verified_at__gte=week_ago,
        verified_at__isnull=False
    ).order_by('-verified_at')[:5]

    for verification in recent_verifications:
        icon = '✅' if verification.status == 'verified' else '❌'
        recent_activity.append({
            'type': 'verification',
            'timestamp': verification.verified_at,
            'title': f"Stats {verification.get_status_display().lower()}",
            'details': f"{verification.get_game_type_display()} - Score: {verification.total_score}",
            'icon': icon
        })

    # Sort activity
    recent_activity.sort(key=lambda x: x['timestamp'], reverse=True)
    recent_activity = recent_activity[:8]

    # Get submissions by game type
    games_summary = {}
    for game_id, game_name in StatSubmission.GAME_CHOICES:
        game_subs = submissions.filter(game_type=game_id)
        if game_subs.exists():
            best_entry = game_subs.order_by('-total_score').first()
            games_summary[game_name] = {
                'count': game_subs.count(),
                'best_score': best_entry.total_score if best_entry else 0,
                'verified_count': game_subs.filter(status='verified').count(),
                'icon': dict(StatSubmission.GAME_CHOICES).get(game_id, '🎮')[0],
                'latest': game_subs.order_by('-created_at').first().created_at if game_subs.exists() else None,
            }

    # Recent submissions for display
    recent_submissions_list = submissions[:10]

    # FIXED: Single context dictionary with favorite_games
    context = {
        'user_profile': user_profile,
        'profile': user_profile_obj,
        'favorite_games': user_profile_obj.favorite_games_display,  # THIS IS CRITICAL

        'submissions': submissions,
        'recent_submissions': recent_submissions_list,
        'recent_activity': recent_activity,
        'has_recent_activity': len(recent_activity) > 0,
        'games_summary': games_summary,

        # Stats
        'total_kills': total_kills,
        'total_deaths': total_deaths,
        'total_wins': total_wins,
        'total_matches_played': total_matches,
        'total_goals': basic_stats['total_goals'] or 0,
        'total_assists': basic_stats['total_assists'] or 0,
        'overall_kd': overall_kd,
        'actual_win_rate': actual_win_rate,
        'total_score': basic_stats['total_score_sum'] or 0,
        'best_score': basic_stats['best_score'] or 0,
        'worst_score': basic_stats['worst_score'] or 0,
        'avg_score': round(avg_score, 1),
        'avg_wins': round(avg_wins, 1),
        'avg_matches': round(avg_matches, 1),

        # Submission stats
        'verified_count': basic_stats['verified_count'] or 0,
        'pending_count': basic_stats['pending_count'] or 0,
        'rejected_count': basic_stats['rejected_count'] or 0,
        'total_submissions': basic_stats['total_submissions'] or 0,
        'games_played': basic_stats['games_played'] or 0,

        # Additional info
        'is_own_profile': request.user == user_profile,
    }

    return render(request, 'core/profile.html', context)
# views.py
from django.contrib.auth.decorators import login_required
from django.shortcuts import render


@login_required
def edit_profile(request):
    # Get user profile
    profile = UserProfile.objects.get_or_create(user=request.user)[0]

    # Get all games
    from .models import Game
    all_games = Game.objects.all()

    # Get currently selected game IDs for the template
    selected_game_ids = []  # Empty list since we don't have favorite_games field anymore
    print(f"DEBUG: User has favorite_game_types: {profile.favorite_game_types}")

    if request.method == 'POST':
        print("=" * 50)
        print("FORM SUBMISSION RECEIVED")
        print("=" * 50)

        # Update user email
        email = request.POST.get('email')
        if email:
            request.user.email = email
            request.user.save()

        # Update profile fields
        profile.bio = request.POST.get('bio', '')
        profile.platform = request.POST.get('platform', 'All')
        profile.play_style = request.POST.get('play_style', 'Competitive')
        profile.preferred_mode = request.POST.get('preferred_mode', 'COMPETITIVE')

        # Get favorite games from form - these are Game IDs
        fav_games_str = request.POST.get('favorite_games', '')
        print(f"DEBUG: Received favorite_games string: '{fav_games_str}'")

        # Process favorite games - FIXED: Convert Game IDs to Game Types
        if fav_games_str:
            # Convert string to list of game IDs
            game_ids = []
            for game_id in fav_games_str.split(','):
                if game_id.strip().isdigit():
                    game_ids.append(int(game_id.strip()))

            print(f"DEBUG: Parsed game IDs: {game_ids}")

            # FIXED: Get Game objects and convert to game types/names
            selected_games = Game.objects.filter(id__in=game_ids)
            game_types = []
            for game in selected_games:
                # Use game.name as the game type
                game_types.append(game.name)

            print(f"DEBUG: Converted to game types: {game_types}")

            # Update favorite game types (limit to 5)
            profile.favorite_game_types = game_types[:5]
        else:
            print("DEBUG: No favorite games selected, clearing all")
            profile.favorite_game_types = []

        # Save the profile
        profile.save()

        print(f"DEBUG: Profile saved. Now has {len(profile.favorite_game_types)} favorite game types")
        print(f"DEBUG: favorite_game_types = {profile.favorite_game_types}")

        print("=" * 50)

        messages.success(request, 'Profile updated successfully!')
        return redirect('profile', username=request.user.username)

    # For GET request, render the form
    # FIXED: We need to convert existing favorite_game_types back to Game IDs for the form
    selected_game_ids = []
    if profile.favorite_game_types:
        # Try to find Game objects that match the favorite_game_types
        for game_type in profile.favorite_game_types:
            try:
                game = Game.objects.filter(name__icontains=game_type).first()
                if game:
                    selected_game_ids.append(str(game.id))
            except:
                pass

    context = {
        'profile': profile,
        'all_games': all_games,
        'selected_game_ids': selected_game_ids,  # For the template to pre-select games
    }

    return render(request, 'core/edit_profile.html', context)
@login_required
def test_profile(request):
    profile = UserProfile.objects.get(user=request.user)
    all_games = Game.objects.all()
    selected_ids = list(profile.favorite_games.values_list('id', flat=True))

    print("=== DEBUG INFO ===")
    print(f"User: {request.user.username}")
    print(f"Total games in DB: {all_games.count()}")
    print(f"Currently selected game IDs: {selected_ids}")

    for game in all_games:
        print(f"Game ID {game.id}: {game.name}")

    if request.method == 'POST':
        print(f"POST data received: {dict(request.POST)}")
        fav_games = request.POST.get('favorite_games', '')
        print(f"Raw favorite_games input: '{fav_games}'")

        # Parse the IDs
        if fav_games:
            ids = [int(i) for i in fav_games.split(',') if i.strip()]
            print(f"Parsed IDs: {ids}")

            # Update the profile
            profile.favorite_games.set(ids[:5])
            profile.save()

            print("Profile saved successfully!")

        return HttpResponse("Test complete - check console")

    context = {
        'games': all_games,
        'selected_ids': selected_ids,
    }
    return render(request, 'core/test_simple.html', context)




# Game info mapping
GAME_INFO = {
    'fifa': {
        'type': 'fifa_mobile',
        'icon': '⚽',
        'name': 'FIFA Mobile',
        'submit_url': 'submit_fifa',
        'template': 'core/leaderboards/fifa.html',
    },
    'pubg': {
        'type': 'pubg_mobile',
        'icon': '🔫',
        'name': 'PUBG Mobile',
        'submit_url': 'submit_pubg',
        'template': 'core/leaderboards/pubg.html',
    },
    'coc': {
        'type': 'clash_of_clans',
        'icon': '🏰',
        'name': 'Clash of Clans',
        'submit_url': 'submit_coc',
        'template': 'core/leaderboards/coc.html',
    },
    'asphalt': {
        'type': 'asphalt_9',
        'icon': '🏎',
        'name': 'Asphalt 9',
        'submit_url': 'submit_asphalt',
        'template': 'core/leaderboards/asphalt.html',
    },
    'ml': {
        'type': 'mobile_legends',
        'icon': '⚔',
        'name': 'Mobile Legends',
        'submit_url': 'submit_ml',
        'template': 'core/leaderboards/mobile_legends.html',
    },
    'dls': {
        'type': 'dream_league_soccer',
        'icon': '🥅',
        'name': 'Dream League Soccer',
        'submit_url': 'submit_dls',
        'template': 'core/leaderboards/dream_league.html',
    },
    'efootball': {
        'type': 'efootball',
        'icon': '🎮',
        'name': 'eFootball',
        'submit_url': 'submit_efootball',
        'template': 'core/leaderboards/efootball.html',
    },
    'cod': {
        'type': 'call_of_duty',
        'icon': '🎯',
        'name': 'Call of Duty',
        'submit_url': 'submit_cod',
        'template': 'core/leaderboards/call_of_duty.html',
    },
}


# ========== LEADERBOARD VIEWS ==========

def leaderboard(request, game_slug):
    game_info = GAME_INFO.get(game_slug)
    if not game_info:
        raise Http404(f"Game '{game_slug}' not found")

    # Get verified submissions
    entries = StatSubmission.objects.filter(
        game_type=game_info['type'],
        status='verified',
        verified=True,
    ).order_by('-total_score')[:100]

    # Add rank numbers (1st, 2nd, 3rd, etc.)
    for i, entry in enumerate(entries, start=1):
        entry.rank = i  # This adds a temporary rank attribute

    context = {
        'entries': entries,
        'game_icon': game_info['icon'],
        'game_name': game_info['name'],
        'submit_url': game_info['submit_url'],
        'game_slug': game_slug,
        'total_players': entries.count(),
    }

    return render(request, game_info['template'], context)

# Individual views (optional - use if you want separate functions)
def fifa_leaderboard(request):
    return leaderboard(request, 'fifa')


def pubg_leaderboard(request):
    return leaderboard(request, 'pubg')


def coc_leaderboard(request):
    return leaderboard(request, 'coc')


def asphalt_leaderboard(request):
    return leaderboard(request, 'asphalt')


def ml_leaderboard(request):
    return leaderboard(request, 'ml')


def dls_leaderboard(request):
    return leaderboard(request, 'dls')


def efootball_leaderboard(request):
    return leaderboard(request, 'efootball')


def cod_leaderboard(request):
    return leaderboard(request, 'cod')


# ========== SUBMIT VIEWS ==========

@login_required
def submit_fifa_stats(request):
    if request.method == 'POST':
        submission = StatSubmission.objects.create(
            user=request.user,
            game_type='fifa_mobile',
            wins=int(request.POST.get('wins', 0)),
            matches_played=int(request.POST.get('matches_played', 0)),
            goals=int(request.POST.get('goals', 0)),
            assists=int(request.POST.get('assists', 0)),
            screenshot=request.FILES.get('screenshot'),
            description=request.POST.get('description', ''),
        )
        submission.calculate_score()
        return redirect('fifa_leaderboard')
    return render(request, 'core/submit/fifa.html')


@login_required
def submit_pubg_stats(request):
    if request.method == 'POST':
        submission = StatSubmission.objects.create(
            user=request.user,
            game_type='pubg_mobile',
            wins=int(request.POST.get('wins', 0)),
            matches_played=int(request.POST.get('matches_played', 0)),
            kills=int(request.POST.get('kills', 0)),
            deaths=int(request.POST.get('deaths', 0)),
            screenshot=request.FILES.get('screenshot'),
            description=request.POST.get('description', ''),
        )
        submission.calculate_score()
        return redirect('pubg_leaderboard')
    return render(request, 'core/submit/pubg.html')


@login_required
def submit_coc_stats(request):
    if request.method == 'POST':
        submission = StatSubmission.objects.create(
            user=request.user,
            game_type='clash_of_clans',
            wins=int(request.POST.get('wins', 0)),
            matches_played=int(request.POST.get('matches_played', 0)),
            trophies=int(request.POST.get('trophies', 0)),
            town_hall_level=int(request.POST.get('town_hall_level', 1)),
            screenshot=request.FILES.get('screenshot'),
            description=request.POST.get('description', ''),
        )
        submission.calculate_score()
        return redirect('coc_leaderboard')
    return render(request, 'core/submit/coc.html')


@login_required
def submit_asphalt_stats(request):
    if request.method == 'POST':
        submission = StatSubmission.objects.create(
            user=request.user,
            game_type='asphalt_9',
            wins=int(request.POST.get('wins', 0)),
            matches_played=int(request.POST.get('matches_played', 0)),
            screenshot=request.FILES.get('screenshot'),
            description=request.POST.get('description', ''),
        )
        submission.calculate_score()
        return redirect('asphalt_leaderboard')
    return render(request, 'core/submit/asphalt.html')


@login_required
def submit_ml_stats(request):
    if request.method == 'POST':
        submission = StatSubmission.objects.create(
            user=request.user,
            game_type='mobile_legends',
            wins=int(request.POST.get('wins', 0)),
            matches_played=int(request.POST.get('matches_played', 0)),
            kills=int(request.POST.get('kills', 0)),
            assists=int(request.POST.get('assists', 0)),
            screenshot=request.FILES.get('screenshot'),
            description=request.POST.get('description', ''),
        )
        submission.calculate_score()
        return redirect('ml_leaderboard')
    return render(request, 'core/submit/mobile_legends.html')


@login_required
def submit_dls_stats(request):
    if request.method == 'POST':
        submission = StatSubmission.objects.create(
            user=request.user,
            game_type='dream_league_soccer',
            wins=int(request.POST.get('wins', 0)),
            matches_played=int(request.POST.get('matches_played', 0)),
            goals=int(request.POST.get('goals', 0)),
            assists=int(request.POST.get('assists', 0)),
            screenshot=request.FILES.get('screenshot'),
            description=request.POST.get('description', ''),
        )
        submission.calculate_score()
        return redirect('dls_leaderboard')
    return render(request, 'core/submit/dream_league.html')


@login_required
def submit_efootball_stats(request):
    if request.method == 'POST':
        submission = StatSubmission.objects.create(
            user=request.user,
            game_type='efootball',
            wins=int(request.POST.get('wins', 0)),
            matches_played=int(request.POST.get('matches_played', 0)),
            goals=int(request.POST.get('goals', 0)),
            screenshot=request.FILES.get('screenshot'),
            description=request.POST.get('description', ''),
        )
        submission.calculate_score()
        return redirect('efootball_leaderboard')
    return render(request, 'core/submit/efootball.html')


@login_required
def submit_cod_stats(request):
    if request.method == 'POST':
        submission = StatSubmission.objects.create(
            user=request.user,
            game_type='call_of_duty',
            wins=int(request.POST.get('wins', 0)),
            matches_played=int(request.POST.get('matches_played', 0)),
            kills=int(request.POST.get('kills', 0)),
            screenshot=request.FILES.get('screenshot'),
            description=request.POST.get('description', ''),
        )
        submission.calculate_score()
        return redirect('cod_leaderboard')
    return render(request, 'core/submit/call_of_duty.html')


# ========== OTHER VIEWS ==========

def select_game(request):
    """Game selection page"""
    return render(request, 'core/select_game.html')


@login_required
def my_submissions(request):
    """User can see their submission status"""
    submissions = StatSubmission.objects.filter(
        user=request.user
    ).order_by('-created_at')

    # Stats
    stats = {
        'total': submissions.count(),
        'verified': submissions.filter(status='verified').count(),
        'pending': submissions.filter(status='pending').count(),
        'rejected': submissions.filter(status='rejected').count(),
    }

    return render(request, 'core/my_submissions.html', {
        'submissions': submissions,
        'stats': stats,
    })




@csrf_exempt
def contact_view(request):
    if request.method == 'POST':
        form = ContactForm(request.POST)
        if form.is_valid():
            name = form.cleaned_data['name']
            email = form.cleaned_data['email']
            subject = form.cleaned_data['subject']
            message = form.cleaned_data['message']

            # Email subject
            subject_choices = dict(form.fields['subject'].choices)
            subject_full = f"Gaming Hub Contact: {subject_choices[subject]}"

            # Email body
            email_body = f"""
            Name: {name}
            Email: {email}
            Subject: {subject_choices[subject]}

            Message:
            {message}

            ---
            This message was sent from the Gaming Hub contact form.
            """

            try:
                # Send email to your support team
                send_mail(
                    subject_full,
                    email_body,
                    email,  # From email (user's email)
                    ['support@gaminghub.com'],  # Your support email
                    fail_silently=False,
                )

                # Send confirmation email to user
                send_mail(
                    "Thanks for contacting Gaming Hub Support!",
                    f"Hi {name},\n\nThank you for contacting Gaming Hub Support. "
                    f"We've received your message and will respond within 2-4 hours.\n\n"
                    f"Your message:\n{message}\n\n"
                    f"Best regards,\nThe Gaming Hub Team",
                    'support@gaminghub.com',
                    [email],
                    fail_silently=False,
                )

                messages.success(request, 'Thank you! Your message has been sent. We\'ll respond within 24 hours.')
                return redirect('contact')  # Redirect to clear form

            except BadHeaderError:
                return HttpResponse('Invalid header found.')
            except Exception as e:
                messages.error(request, f'There was an error sending your message: {str(e)}')
    else:
        form = ContactForm()

    return render(request, 'core/contact.html', {'form': form})