from django.urls import path
from . import views

urlpatterns = [
    path('', views.clash_royale_leaderboard, name='clash_royale_leaderboard'),
    path('connect/', views.connect_account, name='connect_clash_royale'),
    path('refresh/', views.refresh_stats, name='refresh_clash_royale'),
    path('about/', views.about_clash_royale, name='about_clash_royale'),
    path('toggle-data-source/', views.toggle_data_source, name='toggle_data_source'),

]
