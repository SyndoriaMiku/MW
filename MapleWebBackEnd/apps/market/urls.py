from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ListingViewSet, TradeViewSet

router = DefaultRouter()
router.register(r'listings', ListingViewSet, basename='listing')
router.register(r'trades', TradeViewSet, basename='trade')

urlpatterns = [
    path('', include(router.urls)),
]
