from django.urls import path
from . import views

app_name = 'battles'

urlpatterns = [
    path('<str:combat_id>/', views.get_battle_state, name='battle-state'),
    path('<str:combat_id>/action/', views.player_action, name='player-action'),
]
