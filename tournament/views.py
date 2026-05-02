# tournament/views.py - Updated to handle missing TournamentReward
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from .models import TournamentSubscription
from django.shortcuts import render, get_object_or_404
from .models import Tournament, TournamentResult, Match


def tournament_list(request):
    """Display all tournaments"""
    tournaments = Tournament.objects.all().order_by('-start_date')
    return render(request, 'tournament/tournament_list.html', {
        'tournaments': tournaments
    })


def tournament_detail(request, tournament_id):
    """Display tournament details"""
    tournament = get_object_or_404(Tournament, id=tournament_id)

    # Try to get rewards, or use default
    rewards = []
    try:
        # Try to import TournamentReward if it exists
        from .models import TournamentReward
        rewards = TournamentReward.objects.filter(tournament=tournament)
    except ImportError:
        # Create default rewards if TournamentReward doesn't exist
        game_prize_float = float(tournament.game_prize)
        rewards = [
            {'position': 1, 'reward_amount': game_prize_float * 0.5, 'reward_description': 'First Place'},
            {'position': 2, 'reward_amount': game_prize_float * 0.3, 'reward_description': 'Second Place'},
            {'position': 3, 'reward_amount': game_prize_float * 0.2, 'reward_description': 'Third Place'},
        ]

    # Check if user is subscribed
    is_subscribed = False
    user_subscription = None

    if request.user.is_authenticated:
        try:
            user_subscription = TournamentSubscription.objects.get(
                user=request.user,
                tournament=tournament
            )
            is_subscribed = True
        except TournamentSubscription.DoesNotExist:
            pass

    return render(request, 'tournament/tournament_detail.html', {
        'tournament': tournament,
        'rewards': rewards,
        'is_subscribed': is_subscribed,
        'user_subscription': user_subscription,
    })


@login_required
def tournament_payment(request, tournament_id):
    """Display payment page for tournament"""
    tournament = get_object_or_404(Tournament, id=tournament_id)

    # Check if already subscribed
    if TournamentSubscription.objects.filter(user=request.user, tournament=tournament).exists():
        messages.info(request, 'You are already registered!')
        return redirect('tournament_detail', tournament_id=tournament_id)

    # Check conditions
    if tournament.is_full():
        messages.error(request, 'Tournament is full!')
        return redirect('tournament_detail', tournament_id=tournament_id)

    if not tournament.is_registration_open():
        messages.error(request, 'Registration is closed!')
        return redirect('tournament_detail', tournament_id=tournament_id)

    return render(request, 'tournament/payment.html', {
        'tournament': tournament,
    })


@login_required
def submit_payment(request, tournament_id):
    """Submit payment proof"""
    tournament = get_object_or_404(Tournament, id=tournament_id)

    if request.method == 'POST':
        try:
            # Get form data
            payment_method = request.POST.get('payment_method', 'mobile_money')
            transaction_id = request.POST.get('transaction_id', '').strip()

            # Handle file upload
            payment_proof = None
            if 'payment_proof' in request.FILES:
                payment_proof = request.FILES['payment_proof']

            # Create subscription
            subscription = TournamentSubscription.objects.create(
                user=request.user,
                tournament=tournament,
                payment_method=payment_method,
                transaction_id=transaction_id,
                payment_amount=tournament.entry_fee,
                payment_status='pending',
                payment_proof=payment_proof,
                payer_name=request.user.get_full_name(),
                payer_email=request.user.email,
            )

            messages.success(request,
                             '✅ Payment details submitted! '
                             'Your registration will be confirmed after verification.'
                             )

            return redirect('tournament_detail', tournament_id=tournament_id)

        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            return redirect('tournament_payment', tournament_id=tournament_id)

    return redirect('tournament_detail', tournament_id=tournament_id)


@login_required
def user_tournaments(request):
    """Display user's tournaments"""
    subscriptions = TournamentSubscription.objects.filter(
        user=request.user
    ).select_related('tournament')

    # Organize by status
    upcoming = []
    ongoing = []
    completed = []

    for sub in subscriptions:
        tournament = sub.tournament
        if tournament.status == 'upcoming':
            upcoming.append(tournament)
        elif tournament.status == 'ongoing':
            ongoing.append(tournament)
        elif tournament.status == 'completed':
            completed.append(tournament)

    return render(request, 'tournament/my_tournaments.html', {
        'upcoming_tournaments': upcoming,
        'ongoing_tournaments': ongoing,
        'completed_tournaments': completed,
    })


def tournament_matches(request, tournament_id):
    """Display tournament matches"""
    return render(request, 'tournament/tournament_matches.html', {
        'tournament_id': tournament_id,
    })


from django.shortcuts import render, get_object_or_404, redirect
from decimal import Decimal
from .models import Tournament, TournamentResult, Match


def tournament_results(request, tournament_id):
    """Display tournament results"""
    # Get tournament
    tournament = get_object_or_404(Tournament, id=tournament_id)

    # Check if tournament is completed
    if tournament.status != 'completed':
        context = {
            'tournament': tournament,
            'not_completed': True,
        }
        return render(request, 'tournament/results.html', context)

    # Try to get tournament result
    try:
        result = TournamentResult.objects.get(tournament=tournament)
    except TournamentResult.DoesNotExist:
        result = None

        # Get ALL matches (for total count)
    all_matches = Match.objects.filter(tournament=tournament)

    # Get completed matches
    completed_matches = Match.objects.filter(
        tournament=tournament,
        status='completed'
    ).select_related('player1', 'player2', 'winner').order_by('round_number', 'match_number')

    # Get rewards - try TournamentReward model or create defaults
    rewards = []

    # Try to get rewards from TournamentReward model
    try:
        from .models import TournamentReward
        rewards = list(TournamentReward.objects.filter(tournament=tournament).order_by('position'))
    except (ImportError, AttributeError):
        # TournamentReward model doesn't exist
        pass

    # If no rewards from model, create defaults from game_prize
    if not rewards and hasattr(tournament, 'game_prize') and tournament.game_prize:
        try:
            # Ensure game_prize is Decimal
            prize_pool = tournament.game_prize
            if not isinstance(prize_pool, Decimal):
                prize_pool = Decimal(str(prize_pool))

            rewards = [
                {
                    'position': 1,
                    'reward_amount': (prize_pool * Decimal('0.5')).quantize(Decimal('0.01')),
                    'reward_description': 'First Place'
                },
                {
                    'position': 2,
                    'reward_amount': (prize_pool * Decimal('0.3')).quantize(Decimal('0.01')),
                    'reward_description': 'Second Place'
                },
                {
                    'position': 3,
                    'reward_amount': (prize_pool * Decimal('0.2')).quantize(Decimal('0.01')),
                    'reward_description': 'Third Place'
                },
            ]
        except Exception as e:
            print(f"Error creating rewards: {e}")
            rewards = []

    # Alternative: If game_prize doesn't exist, use hardcoded rewards
    if not rewards:
        rewards = [
            {'position': 1, 'reward_amount': Decimal('500.00'), 'reward_description': 'First Place'},
            {'position': 2, 'reward_amount': Decimal('300.00'), 'reward_description': 'Second Place'},
            {'position': 3, 'reward_amount': Decimal('200.00'), 'reward_description': 'Third Place'},
        ]

    context = {
        'tournament': tournament,
        'result': result,  # Could be None
        'completed_matches': completed_matches,  # QuerySet
        'rewards': rewards,  # List or QuerySet
        'all_matches': all_matches,
    }

    return render(request, 'tournament/results.html', context)


# In tournament/views.py
def match_results(request, tournament_id):
    """Show match results for everyone (no registration required)"""
    tournament = get_object_or_404(Tournament, id=tournament_id)

    # Get all matches for this tournament
    matches = Match.objects.filter(tournament=tournament).select_related(
        'player1', 'player2', 'winner'
    ).order_by('round_number', 'match_number')

    context = {
        'tournament': tournament,
        'matches': matches,
    }

    return render(request, 'tournament/match_results.html', context)


@login_required
def payment_status(request, subscription_id):
    """Display payment status"""
    subscription = get_object_or_404(TournamentSubscription, id=subscription_id, user=request.user)
    return render(request, 'tournament/payment_status.html', {
        'subscription': subscription,
        'tournament': subscription.tournament,
    })


@login_required
def user_payment_history(request):
    """User's payment history"""
    subscriptions = TournamentSubscription.objects.filter(
        user=request.user
    ).select_related('tournament').order_by('-subscription_date')

    return render(request, 'tournament/payment_history.html', {
        'subscriptions': subscriptions,
    })



@login_required
def subscribe_tournament(request, tournament_id):
    """Handle tournament subscription (legacy function - redirects to payment)"""
    tournament = get_object_or_404(Tournament, id=tournament_id)

    # Check if already subscribed
    if TournamentSubscription.objects.filter(user=request.user, tournament=tournament).exists():
        messages.info(request, 'You are already registered for this tournament!')
        return redirect('tournament_detail', tournament_id=tournament_id)

    # Check conditions
    if tournament.is_full():
        messages.error(request, 'Tournament is full!')
        return redirect('tournament_detail', tournament_id=tournament_id)

    if not tournament.is_registration_open():
        messages.error(request, 'Registration is closed!')
        return redirect('tournament_detail', tournament_id=tournament_id)

    # Redirect to payment page
    return redirect('tournament_payment', tournament_id=tournament_id)  # tournament/views.py - Add this function


@login_required
def subscribe_tournament(request, tournament_id):
    """Show subscription confirmation page"""
    tournament = get_object_or_404(Tournament, id=tournament_id)

    # Check conditions
    if TournamentSubscription.objects.filter(user=request.user, tournament=tournament).exists():
        messages.info(request, 'You are already registered for this tournament!')
        return redirect('tournament_detail', tournament_id=tournament_id)

    if tournament.is_full():
        messages.error(request, 'Tournament is full!')
        return redirect('tournament_detail', tournament_id=tournament_id)

    if not tournament.is_registration_open():
        messages.error(request, 'Registration is closed!')
        return redirect('tournament_detail', tournament_id=tournament_id)

    # Show subscription page instead of redirecting
    if request.method == 'POST':
        # Create subscription
        subscription = TournamentSubscription.objects.create(
            user=request.user,
            tournament=tournament,
            payment_amount=tournament.entry_fee,
            payment_status='pending'
        )
        messages.success(request, 'Successfully registered! Please complete payment.')
        return redirect('tournament_payment', tournament_id=tournament_id)

    context = {
        'tournament': tournament,
        'entry_fee': tournament.entry_fee,
    }
    return render(request, 'tournament/payment.html', context)



def tournament_results(request, tournament_id):
    """Display tournament results"""
    tournament = get_object_or_404(Tournament, id=tournament_id)

    # Check if tournament is completed
    if tournament.status != 'completed':
        # Redirect to tournament detail if not completed
        from django.shortcuts import redirect
        return redirect('tournament_detail', pk=tournament_id)

    # Get tournament result
    result = get_object_or_404(TournamentResult, tournament=tournament)

    # Get all matches for this tournament
    matches = Match.objects.filter(tournament=tournament).select_related('player1', 'player2', 'winner')

    # Get completed matches
    completed_matches = matches.filter(status='completed')

    context = {
        'tournament': tournament,
        'result': result,
        'matches': completed_matches,
        'all_matches': matches,
    }

    return render(request, 'tournament/results.html', context)


def match_results(request, tournament_id):
    """Display individual match results"""
    tournament = get_object_or_404(Tournament, id=tournament_id)
    matches = Match.objects.filter(tournament=tournament).select_related('player1', 'player2', 'winner')

    context = {
        'tournament': tournament,
        'matches': matches,
    }

    return render(request, 'tournament/match_results.html', context)

