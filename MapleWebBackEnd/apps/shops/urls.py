from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ShopCategoryViewSet, ShopItemViewSet, SpecialShopViewSet

router = DefaultRouter()
router.register(r'categories', ShopCategoryViewSet, basename='shop-category')
router.register(r'items', ShopItemViewSet, basename='shop-item')
router.register(r'special', SpecialShopViewSet, basename='special-shop')

urlpatterns = [
    path('', include(router.urls)),
]
