from django.urls import path
from .views import MyCharacterView

urlpatterns = [
    path('', MyCharacterView.as_view({'post': 'create'}), name='character-create'),
    path('my/', MyCharacterView.as_view({'get': 'my'}), name='my-character'),
]
