"""
URL configuration for MapleWebBackEnd project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include

from rest_framework import permissions
from drf_yasg.views import get_schema_view
from drf_yasg import openapi

schema_view = get_schema_view(
   openapi.Info(
      title="MapleWeb API",
      default_version='v1',
      description="API documentation for MapleWeb Backend",
   ),
   public=True,
   permission_classes=(permissions.AllowAny,),
)

urlpatterns = [
    path('admin/', admin.site.urls),
    path('swagger/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('api/users/', include('apps.users.urls')),
    path('api/classes/', include('apps.classes.urls')),
    path('api/characters/', include('apps.characters.urls')),
    path('api/inventory/', include('apps.inventory.urls')),
    path('api/items/', include('apps.items.urls')),
    path('api/party/', include('apps.party.urls')),
    path('api/world/', include('apps.world.urls')),
    path('api/market/', include('apps.market.urls')),
    path('api/shops/', include('apps.shops.urls')),
]
