from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import ItemTemplateViewSet, LumenAPIView, AuroraAPIView

router = DefaultRouter()
router.register(r'templates', ItemTemplateViewSet, basename='item-template')

urlpatterns = [
    path('', include(router.urls)),
    path('lumen/<str:action>/', LumenAPIView.as_view(), name='lumen-api'),
    path('aurora/<str:action>/', AuroraAPIView.as_view(), name='aurora-api'),
]
