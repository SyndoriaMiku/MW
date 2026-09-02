from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import NormalDungeonViewSet, BossDungeonViewSet

router = DefaultRouter()
router.register(r'normal-dungeons', NormalDungeonViewSet, basename='normal-dungeon')
router.register(r'boss-dungeons', BossDungeonViewSet, basename='boss-dungeon')

urlpatterns = [
    path('', include(router.urls)),
]
