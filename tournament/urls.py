# tournament/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('', views.tournament_list, name='tournament_list'),
    path('<int:tournament_id>/', views.tournament_detail, name='tournament_detail'),
    path('<int:tournament_id>/subscribe/', views.subscribe_tournament, name='subscribe_tournament'),
    path('my-tournaments/', views.user_tournaments, name='user_tournaments'),
    path('<int:tournament_id>/results/', views.tournament_results, name='results'),
    path('<int:tournament_id>/match-results/', views.match_results, name='match_results'),

    path('<int:tournament_id>/payment/', views.tournament_payment, name='tournament_payment'),


    # Payment URLs
    path('<int:tournament_id>/payment/submit/', views.submit_payment, name='submit_payment'),
    path('payment/status/<int:subscription_id>/', views.payment_status, name='payment_status'),
    path('payment/history/', views.user_payment_history, name='user_payment_history'),

    # Admin payment URLs



]

