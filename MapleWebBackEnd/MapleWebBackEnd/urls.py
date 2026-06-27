"""
URL configuration for MapleWebBackEnd project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
"""
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
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
