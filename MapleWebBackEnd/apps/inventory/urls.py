from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import InventoryViewSet, EquippedItemViewSet

router = DefaultRouter()
router.register(r'equipped', EquippedItemViewSet, basename='equipped-item')
router.register(r'', InventoryViewSet, basename='inventory-item')

urlpatterns = [
    path('', include(router.urls)),
]
