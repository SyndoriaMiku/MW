from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import PartyViewSet

router = DefaultRouter()
router.register(r'party', PartyViewSet, basename='party')

urlpatterns = [
    path('', include(router.urls)),
]
