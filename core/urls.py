from django.urls import path
from django.contrib.auth import views as auth_views
from . import views
from django.views.generic import TemplateView
from django.urls import path, include



urlpatterns = [
    path('', views.home, name='home'),
    path('games/', views.game_list, name='game_list'),
    path('games/<int:pk>/', views.game_detail, name='game_detail'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    path('my-submissions/', views.my_submissions, name='my_submissions'),
    path('about/', TemplateView.as_view(template_name='core/about.html'), name='about'),
    path('contact/', TemplateView.as_view(template_name='core/contact.html'), name='contact'),
    path('terms/', TemplateView.as_view(template_name='core/terms.html'), name='terms'),
    path('privacy/', TemplateView.as_view(template_name='core/privacy.html'), name='privacy'),
    path('profile/<str:username>/', views.profile_view, name='profile'),
    path('profile/edit/,', views.edit_profile, name='edit_profile'),
    path('test-profile/', views.test_profile, name='core/test_profile'),
    path('clash-royale/', include('clashroyale.urls')),
    path('games/', views.select_game, name='select_game'),

    # urls.py - ALL 16 URLs (8 submit + 8 leaderboard)

    # Submit URLs
    path('submit/fifa/', views.submit_fifa_stats, name='submit_fifa'),
    path('submit/pubg/', views.submit_pubg_stats, name='submit_pubg'),
    path('submit/clash-of-clans/', views.submit_coc_stats, name='submit_coc'),
    path('submit/asphalt-9/', views.submit_asphalt_stats, name='submit_asphalt'),
    path('submit/mobile-legends/', views.submit_ml_stats, name='submit_ml'),
    path('submit/dream-league/', views.submit_dls_stats, name='submit_dls'),
    path('submit/efootball/', views.submit_efootball_stats, name='submit_efootball'),
    path('submit/call-of-duty/', views.submit_cod_stats, name='submit_cod'),
    path('tournament/', include('tournament.urls')),

# === LEADERBOARDS (8 total) ===
    # Option A: Individual URLs (recommended)
    path('leaderboards/fifa/', views.fifa_leaderboard, name='fifa_leaderboard'),
    path('leaderboards/pubg/', views.pubg_leaderboard, name='pubg_leaderboard'),
    path('leaderboards/clash-of-clans/', views.coc_leaderboard, name='coc_leaderboard'),
    path('leaderboards/asphalt-9/', views.asphalt_leaderboard, name='asphalt_leaderboard'),
    path('leaderboards/mobile-legends/', views.ml_leaderboard, name='ml_leaderboard'),
    path('leaderboards/dream-league/', views.dls_leaderboard, name='dls_leaderboard'),
    path('leaderboards/efootball/', views.efootball_leaderboard, name='efootball_leaderboard'),
    path('leaderboards/call-of-duty/', views.cod_leaderboard, name='cod_leaderboard'),




    # Room URLs (using room codes instead of IDs)
    path('rooms/', views.room_list, name='room_list'),
    path('rooms/create/', views.create_room, name='create_room'),
    path('rooms/<str:room_code>/', views.room_detail, name='room_detail'),
    path('rooms/<str:room_code>/join/', views.join_room, name='join_room'),
    path('rooms/<str:room_code>/leave/', views.leave_room, name='leave_room'),







    path('password-reset/',
         auth_views.PasswordResetView.as_view(
             template_name='core/password_reset.html',
             email_template_name='core/password_reset_email.html',
             subject_template_name='core/password_reset_subject.txt'
         ),
         name='password_reset'),

    path('password-reset/done/',
         auth_views.PasswordResetDoneView.as_view(
             template_name='core/password_reset_done.html'
         ),
         name='password_reset_done'),

    path('password-reset-confirm/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='core/password_reset_confirm.html'
         ),
         name='password_reset_confirm'),

    path('password-reset-complete/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='core/password_reset_complete.html'
         ),
         name='password_reset_complete'),
]