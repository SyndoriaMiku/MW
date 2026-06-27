from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import CharacterClassViewSet, JobViewSet

router = DefaultRouter()
router.register(r'jobs', JobViewSet, basename='job')
router.register(r'', CharacterClassViewSet, basename='characterclass')

urlpatterns = [
    path('', include(router.urls)),
]
