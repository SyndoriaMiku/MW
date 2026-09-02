from django.urls import path
from . import views

app_name = 'quests'

urlpatterns = [
    path('', views.quest_list, name='quest-list'),
    path('<int:quest_id>/claim/', views.claim_quest_reward, name='claim-quest'),
]
