from django.urls import path
from .views import MyCharacterView

urlpatterns = [
    path('', MyCharacterView.as_view({'post': 'create'}), name='character-create'),
    path('my/', MyCharacterView.as_view({'get': 'my'}), name='my-character'),
    path('my/skills/', MyCharacterView.as_view({'get': 'my_skills'}), name='my-skills'),
    path(
        'my/skills/<int:char_skill_id>/upgrade/',
        MyCharacterView.as_view({'post': 'upgrade_skill'}),
        name='upgrade-skill',
    ),
]
