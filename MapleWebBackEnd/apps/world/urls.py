from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BossDungeonViewSet, LocationViewSet, NormalDungeonViewSet, RegionViewSet

router = DefaultRouter()
router.register(r'normal-dungeons', NormalDungeonViewSet, basename='normal-dungeon')
router.register(r'boss-dungeons', BossDungeonViewSet, basename='boss-dungeon')
router.register(r'regions', RegionViewSet, basename='region')
router.register(r'locations', LocationViewSet, basename='location')

urlpatterns = [
    path('', include(router.urls)),
]
