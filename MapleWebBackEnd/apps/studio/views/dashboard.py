from django.db.models import Q
from django.shortcuts import render
from django.urls import reverse
from django.views import View

from apps.classes.models import CharacterClass, Job
from apps.items.models import AuroraLumisCostRule, ItemTemplate
from apps.quests.models import QuestTemplate
from apps.shops.models import ShopItem, SpecialShopItem
from apps.skilles.models import EffectTemplate, SkillTemplate
from apps.world.models import BossDungeonTemplate, EnemyTemplate, NormalDungeonTemplate

from ..access import StaffRequiredMixin
from ..items_logic import USE_RULE_RELATIONS


def configuration_checks():
    """Data problems that break or weaken gameplay, each with where to fix it."""
    checks = []

    def add(objects, message, url_name):
        names = [getattr(obj, 'name', None) or str(obj) for obj in objects[:6]]
        if names:
            checks.append({'message': message, 'names': names, 'count': len(objects), 'url': reverse(url_name)})

    add(list(CharacterClass.objects.filter(job__isnull=True)), 'Class chưa có job nào (không tạo được nhân vật class này).', 'studio:class-list')
    add(list(Job.objects.filter(Q(weapon_type__isnull=True) | Q(weapon_type=''))), 'Job chưa chọn loại vũ khí (đang cầm được mọi vũ khí).', 'studio:class-list')
    players = [SkillTemplate.Availability.PLAYER, SkillTemplate.Availability.BOTH]
    with_basic = SkillTemplate.objects.filter(is_basic_attack=True, availability__in=players).values('job')
    add(list(Job.objects.exclude(pk__in=with_basic)), 'Job chưa có đòn đánh thường (skill "basic attack").', 'studio:skill-list')
    no_rule = Q()
    for relation in USE_RULE_RELATIONS.values():
        no_rule &= Q(**{f'{relation}__isnull': True})
    add(list(ItemTemplate.objects.filter(no_rule, item_type='use')), 'Item tiêu hao chưa có công dụng (dùng không được).', 'studio:item-list')
    add(list(NormalDungeonTemplate.objects.filter(stage_enemies__isnull=True)), 'Dungeon thường chưa có quái (người chơi không vào được).', 'studio:dungeon-list')
    add(list(BossDungeonTemplate.objects.filter(stage_enemies__isnull=True)), 'Dungeon boss chưa có quái (người chơi không vào được).', 'studio:dungeon-list')
    add(list(EnemyTemplate.objects.filter(loot_tables__isnull=True)), 'Quái chưa rơi đồ gì.', 'studio:enemy-list')
    if not ShopItem.objects.exists():
        checks.append({
            'message': 'Chưa có shop bán gì: người chơi chưa có chỗ tiêu Lumis.',
            'names': [], 'count': 0, 'url': reverse('studio:shop-list'),
        })
    add(list(SpecialShopItem.objects.filter(specialshopitemrecipe__isnull=True)),
        'Món ở shop đặc biệt chưa có nguyên liệu (không đổi được).', 'studio:shop-list')
    if not AuroraLumisCostRule.objects.exists():
        checks.append({
            'message': 'Chưa có bảng giá reroll Aurora bằng Lumis (người chơi chỉ reroll bằng đá được).',
            'names': [], 'count': 0, 'url': reverse('studio:aurora-lumis-costs'),
        })
    return checks


class DashboardView(StaffRequiredMixin, View):
    def get(self, request):
        tiles = [
            ('Item', ItemTemplate.objects.count(), 'studio:item-list'),
            ('Class', CharacterClass.objects.count(), 'studio:class-list'),
            ('Job', Job.objects.count(), 'studio:class-list'),
            ('Skill', SkillTemplate.objects.count(), 'studio:skill-list'),
            ('Hiệu ứng', EffectTemplate.objects.count(), 'studio:effect-list'),
            ('Quái vật', EnemyTemplate.objects.count(), 'studio:enemy-list'),
            ('Dungeon', NormalDungeonTemplate.objects.count() + BossDungeonTemplate.objects.count(), 'studio:dungeon-list'),
            ('Món bán ở shop', ShopItem.objects.count() + SpecialShopItem.objects.count(), 'studio:shop-list'),
            ('Quest', QuestTemplate.objects.count(), 'studio:quest-list'),
        ]
        return render(request, 'studio/dashboard.html', {
            'section': 'dashboard',
            'tiles': [{'label': label, 'count': count, 'url': reverse(url)} for label, count, url in tiles],
            'checks': configuration_checks(),
        })
