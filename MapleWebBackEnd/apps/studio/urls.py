from django.urls import path

from .views import characters, dashboard, items, world

app_name = 'studio'


def crud(prefix, name, editor, delete, list_view):
    return [
        path(f'{prefix}/', list_view.as_view(), name=f'{name}-list'),
        path(f'{prefix}/new/', editor.as_view(), name=f'{name}-new'),
        path(f'{prefix}/<int:pk>/', editor.as_view(), name=f'{name}-edit'),
        path(f'{prefix}/<int:pk>/delete/', delete.as_view(), name=f'{name}-delete'),
    ]


urlpatterns = [
    path('', dashboard.DashboardView.as_view(), name='dashboard'),
    *crud('items', 'item', items.ItemEditorView, items.ItemDeleteView, items.ItemListView),
    path('items/suggest/', items.ItemSuggestView.as_view(), name='item-suggest'),
    path('items/estimate/', items.ItemEstimateView.as_view(), name='item-estimate'),
    path('items/<int:pk>/clone/', items.ItemCloneView.as_view(), name='item-clone'),
    *crud('classes', 'class', characters.ClassEditorView, characters.ClassDeleteView, characters.ClassListView),
    *crud('skills', 'skill', characters.SkillEditorView, characters.SkillDeleteView, characters.SkillListView),
    *crud('effects', 'effect', characters.EffectEditorView, characters.EffectDeleteView, characters.EffectListView),
    *crud('enemies', 'enemy', world.EnemyEditorView, world.EnemyDeleteView, world.EnemyListView),
    path('dungeons/', world.DungeonListView.as_view(), name='dungeon-list'),
    path('dungeons/<str:kind>/new/', world.DungeonEditorView.as_view(), name='dungeon-new'),
    path('dungeons/<str:kind>/<int:pk>/', world.DungeonEditorView.as_view(), name='dungeon-edit'),
    path('dungeons/<str:kind>/<int:pk>/delete/', world.DungeonDeleteView.as_view(), name='dungeon-delete'),
    *crud('regions', 'region', world.RegionEditorView, world.RegionDeleteView, world.RegionListView),
]
