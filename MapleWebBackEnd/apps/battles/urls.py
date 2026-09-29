from django.urls import path
from . import views

app_name = 'battles'

urlpatterns = [
    path('active/', views.get_active_battle, name='active-battle'),
    path('<str:combat_id>/', views.get_battle_state, name='battle-state'),
    path('<str:combat_id>/action/', views.player_action, name='player-action'),
    path('<str:combat_id>/forfeit/', views.forfeit_battle, name='forfeit'),
    path('<str:combat_id>/skip-idle-turn/', views.skip_idle_turn, name='skip-idle-turn'),
]
