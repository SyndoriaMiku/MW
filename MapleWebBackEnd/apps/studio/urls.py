from django.urls import path

from .views import characters, content, dashboard, history, items, ops, players, tables, tiers, world

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
    path('history/', history.HistoryView.as_view(), name='history'),
    path('players/', players.PlayerListView.as_view(), name='player-list'),
    path('players/<int:pk>/', players.PlayerDetailView.as_view(), name='player-detail'),
    path('ops/market/', ops.MarketView.as_view(), name='ops-market'),
    path('ops/parties/', ops.PartyListView.as_view(), name='ops-parties'),
    path('ops/battles/', ops.BattleListView.as_view(), name='ops-battles'),
    path('ops/boss-clears/', ops.BossClearListView.as_view(), name='ops-boss-clears'),
    path('ops/character-quests/', ops.CharacterQuestListView.as_view(), name='ops-character-quests'),
    path('settings/experience/', tables.ExperienceTableView.as_view(), name='experience-table'),
    path('settings/equipment-slots/', tables.EquipmentSlotTableView.as_view(), name='equipment-slots'),
    path('settings/effect-tags/', tables.SpecialEffectTagTableView.as_view(), name='effect-tags'),
    path('settings/aurora-lines/', tables.AuroraLineCountTableView.as_view(), name='aurora-line-counts'),
    path('settings/aurora-lumis/', tables.AuroraLumisCostTableView.as_view(), name='aurora-lumis-costs'),
    *crud('items', 'item', items.ItemEditorView, items.ItemDeleteView, items.ItemListView),
    path('items/suggest/', items.ItemSuggestView.as_view(), name='item-suggest'),
    path('items/estimate/', items.ItemEstimateView.as_view(), name='item-estimate'),
    path('items/<int:pk>/clone/', items.ItemCloneView.as_view(), name='item-clone'),
    *crud('lumen-tiers', 'lumen', tiers.LumenTierEditorView, tiers.LumenTierDeleteView, tiers.LumenTierListView),
    path('lumen-tiers/<int:pk>/copy/', tiers.LumenTierCopyView.as_view(), name='lumen-copy'),
    *crud('aurora-tiers', 'aurora', tiers.AuroraTierEditorView, tiers.AuroraTierDeleteView, tiers.AuroraTierListView),
    path('aurora-tiers/<int:pk>/copy/', tiers.AuroraTierCopyView.as_view(), name='aurora-copy'),
    *crud('item-sets', 'set', tiers.ItemSetEditorView, tiers.ItemSetDeleteView, tiers.ItemSetListView),
    *crud('classes', 'class', characters.ClassEditorView, characters.ClassDeleteView, characters.ClassListView),
    *crud('skills', 'skill', characters.SkillEditorView, characters.SkillDeleteView, characters.SkillListView),
    *crud('effects', 'effect', characters.EffectEditorView, characters.EffectDeleteView, characters.EffectListView),
    *crud('enemies', 'enemy', world.EnemyEditorView, world.EnemyDeleteView, world.EnemyListView),
    path('dungeons/', world.DungeonListView.as_view(), name='dungeon-list'),
    path('dungeons/<str:kind>/new/', world.DungeonEditorView.as_view(), name='dungeon-new'),
    path('dungeons/<str:kind>/<int:pk>/', world.DungeonEditorView.as_view(), name='dungeon-edit'),
    path('dungeons/<str:kind>/<int:pk>/delete/', world.DungeonDeleteView.as_view(), name='dungeon-delete'),
    *crud('regions', 'region', world.RegionEditorView, world.RegionDeleteView, world.RegionListView),
    path('shops/', content.ShopListView.as_view(), name='shop-list'),
    path('shops/new/', content.ShopCategoryEditorView.as_view(), name='shop-new'),
    path('shops/<int:pk>/', content.ShopCategoryEditorView.as_view(), name='shop-edit'),
    path('shops/<int:pk>/delete/', content.ShopCategoryDeleteView.as_view(), name='shop-delete'),
    path('special-shops/new/', content.SpecialShopEditorView.as_view(), name='special-shop-new'),
    path('special-shops/<int:pk>/', content.SpecialShopEditorView.as_view(), name='special-shop-edit'),
    path('special-shops/<int:pk>/delete/', content.SpecialShopDeleteView.as_view(), name='special-shop-delete'),
    *crud('quests', 'quest', content.QuestEditorView, content.QuestDeleteView, content.QuestListView),
    path('events/', content.EventListView.as_view(), name='event-list'),
    path('events/<str:kind>/new/', content.EventEditorView.as_view(), name='event-new'),
    path('events/<str:kind>/<int:pk>/', content.EventEditorView.as_view(), name='event-edit'),
    path('events/<str:kind>/<int:pk>/delete/', content.EventDeleteView.as_view(), name='event-delete'),
]
