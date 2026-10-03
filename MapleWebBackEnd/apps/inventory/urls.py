from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import BuybackViewSet, InventoryViewSet, EquippedItemViewSet, EquipmentSlotConfigViewSet

router = DefaultRouter()
router.register(r'equipped', EquippedItemViewSet, basename='equipped-item')
router.register(r'slots', EquipmentSlotConfigViewSet, basename='equipment-slot')
router.register(r'buyback', BuybackViewSet, basename='buyback')
router.register(r'', InventoryViewSet, basename='inventory-item')

urlpatterns = [
    path('', include(router.urls)),
]
