from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import SkillTemplateViewSet

router = DefaultRouter()
router.register(r'', SkillTemplateViewSet, basename='skill')

urlpatterns = [
    path('', include(router.urls)),
]
