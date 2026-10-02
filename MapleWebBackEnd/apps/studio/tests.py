from django.test import TestCase
from django.urls import reverse

from apps.characters.models import Character
from apps.classes.models import CharacterClass, Job
from apps.inventory.models import InventoryItem
from apps.items.models import BattleConsumableRule, ItemTemplate, LumenTierProperty, TimedBuffRule
from apps.skilles.models import EffectTemplate, SkillLevelConfig, SkillTemplate
from apps.users.models import GameUser
from apps.world.models import EnemyTemplate, LootTable, NormalDungeonTemplate, Region

from .fields import PercentField


def formset_data(prefix, rows, initial=0):
    """POST data for an inline formset: management form plus one dict per row."""
    data = {
        f'{prefix}-TOTAL_FORMS': str(len(rows)), f'{prefix}-INITIAL_FORMS': str(initial),
        f'{prefix}-MIN_NUM_FORMS': '0', f'{prefix}-MAX_NUM_FORMS': '1000',
    }
    for index, row in enumerate(rows):
        for key, value in row.items():
            data[f'{prefix}-{index}-{key}'] = value
    return data


ITEM_DEFAULTS = {
    'name': 'Item', 'item_type': 'top', 'weapon_type': '', 'minimum_level': 1,
    'str_boost': 0, 'agi_boost': 0, 'int_boost': 0, 'all_stats_boost': 0, 'att_boost': 0,
    'hp_boost': 0, 'mp_boost': 0, 'drop_rate_boost': 0, 'lumen_tier': '', 'aurora_tier': '',
    'is_tradeable': 'on', 'is_sellable': 'on', 'sell_price': 1, 'expire_after_minutes': '', 'expires_at': '',
    'description': '', 'icon_key': '', 'visual_key': '', 'use_kind': '',
}


class StudioTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.staff = GameUser.objects.create_user(username='editor', email='editor@example.com', password='Pass-12345')
        cls.staff.is_staff = True
        cls.staff.save(update_fields=['is_staff'])
        cls.warrior = CharacterClass.objects.create(name='Warrior', main_stat='str', str_growth=2, hp_growth=10)
        cls.archer = CharacterClass.objects.create(name='Archer', main_stat='agi', agi_growth=2)
        cls.fighter = Job.objects.create(name='Fighter', character_class=cls.warrior, weapon_type='2hs')
        cls.bowman = Job.objects.create(name='Bowman', character_class=cls.archer, weapon_type='bow')

    def setUp(self):
        self.client.force_login(self.staff)

    def post_item(self, url=None, **fields):
        data = {**ITEM_DEFAULTS, **fields}
        data = {key: value for key, value in data.items() if value is not None}
        return self.client.post(url or reverse('studio:item-new'), data)


class AccessTests(StudioTestCase):
    def test_anonymous_users_are_sent_to_the_admin_login(self):
        self.client.logout()

        response = self.client.get(reverse('studio:item-list'))

        self.assertRedirects(response, f"{reverse('admin:login')}?next={reverse('studio:item-list')}", fetch_redirect_response=False)

    def test_players_without_staff_rights_are_refused(self):
        player = GameUser.objects.create_user(username='player', email='player@example.com', password='Pass-12345')
        self.client.force_login(player)

        self.assertEqual(self.client.get(reverse('studio:dashboard')).status_code, 403)
        self.assertEqual(self.client.get(reverse('studio:item-estimate')).status_code, 403)

    def test_every_page_opens(self):
        item = ItemTemplate.objects.create(name='Cap', item_type='hat')
        skill = SkillTemplate.objects.create(name='Slash', job=self.fighter)
        effect = EffectTemplate.objects.create(name='Rage')
        enemy = EnemyTemplate.objects.create(
            name='Slime', level=1, base_hp=10, base_mp=0, base_att=1, exp_reward=1, lumis_reward_min=0, lumis_reward_max=1,
        )
        dungeon = NormalDungeonTemplate.objects.create(name='Cave')
        region = Region.objects.create(name='Henesys')
        urls = [
            reverse('studio:dashboard'),
            *[reverse(f'studio:{name}-list') for name in ('item', 'class', 'skill', 'effect', 'enemy', 'dungeon', 'region')],
            *[reverse(f'studio:{name}-new') for name in ('item', 'class', 'skill', 'effect', 'enemy', 'region')],
            reverse('studio:dungeon-new', args=['normal']), reverse('studio:dungeon-new', args=['boss']),
            reverse('studio:item-edit', args=[item.pk]), reverse('studio:item-clone', args=[item.pk]),
            reverse('studio:item-delete', args=[item.pk]), reverse('studio:class-edit', args=[self.warrior.pk]),
            reverse('studio:skill-edit', args=[skill.pk]), reverse('studio:effect-edit', args=[effect.pk]),
            reverse('studio:enemy-edit', args=[enemy.pk]), reverse('studio:dungeon-edit', args=['normal', dungeon.pk]),
            reverse('studio:region-edit', args=[region.pk]),
        ]
        for url in urls:
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)
        self.assertEqual(self.client.get('/studio/dungeons/raid/new/').status_code, 404)


class PercentFieldTests(TestCase):
    def test_shows_fractions_as_percent_and_stores_them_back(self):
        field = PercentField()

        self.assertEqual(field.prepare_value(0.25), 25)
        self.assertEqual(field.prepare_value(0.075), 7.5)
        self.assertEqual(field.prepare_value('12'), '12')  # redisplayed input stays as typed
        self.assertEqual(field.clean('30'), 0.3)


class ItemBuilderTests(StudioTestCase):
    def test_creates_gear_for_a_class(self):
        response = self.post_item(name='Bronze Armor', minimum_level=10, str_boost=6, hp_boost=60, class_restriction=[self.warrior.pk])

        item = ItemTemplate.objects.get(name='Bronze Armor')
        self.assertRedirects(response, reverse('studio:item-edit', args=[item.pk]))
        self.assertEqual((item.str_boost, item.hp_boost), (6, 60))
        self.assertEqual(list(item.class_restriction.all()), [self.warrior])

    def test_refuses_gear_nobody_could_wear(self):
        response = self.post_item(
            name='Odd Sword', item_type='weapon', weapon_type='2hs',
            class_restriction=[self.warrior.pk], job_restriction=[self.bowman.pk],
        )

        self.assertEqual(response.status_code, 200)
        errors = response.context['form'].errors['job_restriction']
        self.assertTrue(any('Bowman thuộc Archer' in error for error in errors))
        self.assertTrue(any('Bowman chỉ cầm' in error for error in errors))
        self.assertFalse(ItemTemplate.objects.filter(name='Odd Sword').exists())

    def test_weapons_still_need_a_weapon_type(self):
        response = self.post_item(name='Stick', item_type='weapon')

        self.assertIn('weapon_type', response.context['form'].errors)

    def test_items_that_are_not_gear_drop_stats_and_restrictions(self):
        response = self.post_item(
            name='Potion', item_type='use', weapon_type='bow', str_boost=9, class_restriction=[self.warrior.pk],
            use_kind='battle', **{'rule_battle-hp_restore': 0, 'rule_battle-hp_restore_percent': 30,
                                  'rule_battle-mp_restore': 0, 'rule_battle-mp_restore_percent': '',
                                  'rule_battle-target_type': 'SELF', 'rule_battle-cooldown_turns': 1},
        )

        item = ItemTemplate.objects.get(name='Potion')
        self.assertRedirects(response, reverse('studio:item-edit', args=[item.pk]))
        self.assertEqual((item.str_boost, item.weapon_type), (0, None))
        self.assertFalse(item.class_restriction.exists())
        # Typed as 30 (%), stored as the fraction the game uses.
        self.assertEqual(item.battle_consumable_rule.hp_restore_percent, 0.3)

    def test_switching_use_kind_replaces_the_rule(self):
        item = ItemTemplate.objects.create(name='Elixir', item_type='use')
        BattleConsumableRule.objects.create(item_template=item, hp_restore=50)

        self.post_item(
            reverse('studio:item-edit', args=[item.pk]), name='Elixir', item_type='use', use_kind='timed_buff',
            **{'rule_timed_buff-exp_rate_bonus': 100, 'rule_timed_buff-lumis_rate_bonus': 0,
               'rule_timed_buff-drop_rate_bonus': 0, 'rule_timed_buff-epic_drop_rate_bonus': 0,
               'rule_timed_buff-final_damage_bonus': 0, 'rule_timed_buff-duration_minutes': 30,
               'rule_timed_buff-max_duration_minutes': ''},
        )

        item.refresh_from_db()
        self.assertFalse(BattleConsumableRule.objects.filter(item_template=item).exists())
        self.assertEqual(TimedBuffRule.objects.get(item_template=item).exp_rate_bonus, 100)

    def test_rule_rules_still_apply(self):
        # A battle consumable must restore something (BattleConsumableRule.clean).
        response = self.post_item(
            name='Empty Flask', item_type='use', use_kind='battle',
            **{'rule_battle-hp_restore': 0, 'rule_battle-mp_restore': 0, 'rule_battle-target_type': 'SELF',
               'rule_battle-cooldown_turns': 0},
        )
        self.assertEqual(response.status_code, 200)
        self.assertFalse(ItemTemplate.objects.filter(name='Empty Flask').exists())

        response = self.post_item(name='Junk', item_type='etc', use_kind='battle')
        self.assertIn('use_kind', response.context['form'].errors)

    def test_suggests_stats_on_the_class_main_stat(self):
        response = self.client.get(reverse('studio:item-suggest'), {'item_type': 'top', 'level': 10, 'main_stat': 'agi'})

        stats = response.json()['stats']
        self.assertGreater(stats['agi_boost'], 0)
        self.assertEqual((stats['str_boost'], stats['int_boost']), (0, 0))
        self.assertEqual(self.client.get(reverse('studio:item-suggest'), {'item_type': 'use'}).json()['stats'], {})

    def test_estimates_damage_with_the_game_formula(self):
        response = self.client.get(reverse('studio:item-estimate'), {
            'job': self.fighter.pk, 'level': 10, 'att_boost': 20, 'str_boost': 0,
        })

        data = response.json()
        # STR 10 + 2 x 9 levels = 28; ATT 5 (+20 from the item). 28 x 5 / 100 rounds to 1.
        self.assertEqual(data['stats'], {'str': 28, 'agi': 10, 'int': 10, 'att': 25})
        self.assertEqual((data['without_item'], data['with_item']), (1, 7))
        self.assertEqual(data['hp'], 50 + 10 * 9)
        self.assertEqual(self.client.get(reverse('studio:item-estimate')).status_code, 400)

    def test_delete_lists_player_copies_first(self):
        item = ItemTemplate.objects.create(name='Shared Ring', item_type='ring')
        InventoryItem.objects.create(owner=Character.objects.create(name='Holder'), template=item)

        page = self.client.get(reverse('studio:item-delete', args=[item.pk]))
        self.assertEqual(sum(page.context['counts'].values()), 1)

        self.client.post(reverse('studio:item-delete', args=[item.pk]))
        self.assertFalse(ItemTemplate.objects.filter(pk=item.pk).exists())


class CloneTests(StudioTestCase):
    def test_armor_copy_moves_the_main_stat_to_the_other_class(self):
        base_tier = LumenTierProperty.objects.create(name='Gear T1', tier=1)
        agi_tier = LumenTierProperty.objects.create(name='Gear T1 (AGI Variant)', tier=1)
        armor = ItemTemplate.objects.create(
            name='Warrior Plate', item_type='top', str_boost=12, hp_boost=80, lumen_tier=base_tier, icon_key='plate',
        )
        armor.class_restriction.set([self.warrior])

        self.client.post(reverse('studio:item-clone', args=[armor.pk]), {'classes': [self.archer.pk]})

        copy = ItemTemplate.objects.get(name='Archer Plate')
        self.assertEqual((copy.str_boost, copy.agi_boost, copy.hp_boost), (0, 12, 80))
        self.assertEqual(list(copy.class_restriction.all()), [self.archer])
        self.assertEqual(copy.lumen_tier, agi_tier)
        self.assertIsNone(copy.icon_key)

    def test_lumen_tiers_named_by_class_follow_the_copy(self):
        warrior_tier = LumenTierProperty.objects.create(name='Tier 1 - Warrior 1-59', tier=1)
        archer_tier = LumenTierProperty.objects.create(name='Tier 1 - Archer 1-59', tier=1)
        boots = ItemTemplate.objects.create(name='Leather Boots', item_type='shoes', str_boost=3, lumen_tier=warrior_tier)
        boots.class_restriction.set([self.warrior])

        self.client.post(reverse('studio:item-clone', args=[boots.pk]), {'classes': [self.archer.pk]})

        copy = ItemTemplate.objects.get(name='Leather Boots (Archer)')
        self.assertEqual((copy.lumen_tier, copy.agi_boost), (archer_tier, 3))

    def test_weapon_copy_follows_the_job_weapon_type(self):
        sword = ItemTemplate.objects.create(name='Great Sword', item_type='weapon', weapon_type='2hs', att_boost=30, str_boost=5)
        sword.class_restriction.set([self.warrior])

        refused = self.client.post(reverse('studio:item-clone', args=[sword.pk]), {'classes': [self.archer.pk]})
        self.assertEqual(refused.status_code, 200)  # weapons need a job

        self.client.post(reverse('studio:item-clone', args=[sword.pk]), {'jobs': [self.bowman.pk]})
        copy = ItemTemplate.objects.get(name='Great Sword (Bowman)')
        self.assertEqual((copy.weapon_type, copy.agi_boost, copy.att_boost), ('bow', 5, 30))
        self.assertEqual(list(copy.job_restriction.all()), [self.bowman])

    def test_plain_copy_keeps_the_use_rule(self):
        potion = ItemTemplate.objects.create(name='Red Potion', item_type='use')
        BattleConsumableRule.objects.create(item_template=potion, hp_restore=50)

        self.client.post(reverse('studio:item-clone', args=[potion.pk]), {'plain_copy': '1'})

        copy = ItemTemplate.objects.get(name='Red Potion (bản sao)')
        self.assertEqual(copy.battle_consumable_rule.hp_restore, 50)
        self.assertEqual(potion.battle_consumable_rule.hp_restore, 50)


class CharacterEditorTests(StudioTestCase):
    def test_class_with_jobs(self):
        data = {
            'name': 'Magician', 'main_stat': 'int', 'hp_growth': 5, 'mp_growth': 10,
            'str_growth': 0, 'agi_growth': 0, 'int_growth': 2.5,
            **formset_data('jobs', [{'name': 'Ignis Mage', 'weapon_type': 'staff', 'main_stat_weight': 1.2}]),
        }

        response = self.client.post(reverse('studio:class-new'), data)

        magician = CharacterClass.objects.get(name='Magician')
        self.assertRedirects(response, reverse('studio:class-edit', args=[magician.pk]))
        job = magician.job_set.get()
        self.assertEqual((job.name, job.weapon_type, job.main_stat_weight), ('Ignis Mage', 'staff', 1.2))

    def skill_data(self, levels, **fields):
        data = {
            'name': 'Power Strike', 'availability': 'PLAYER', 'job': self.fighter.pk, 'required_level': 1,
            'effect_type': 'DAMAGE', 'target_type': 'ENEMY', 'mp_cost': 5, 'cooldown': 0, 'base_power': 10,
            'power_ratio': 120, 'applies_effect': '', 'description': '', 'icon_key': '', 'visual_key': '',
            **formset_data('levels', levels),
        }
        data.update(fields)
        return data

    def test_skill_with_levels_in_percent(self):
        stone = ItemTemplate.objects.create(name='Skill Stone', item_type='etc')
        levels = [
            {'skill_level': 1, 'required_char_level': 1, 'damage_multiplier': 100, 'final_damage_bonus': '', 'required_materials': '[]'},
            {'skill_level': 2, 'required_char_level': 10, 'damage_multiplier': 150, 'final_damage_bonus': '',
             'required_materials': f'[{{"item_template_id": {stone.pk}, "quantity": 3}}]'},
        ]

        self.client.post(reverse('studio:skill-new'), self.skill_data(levels))

        skill = SkillTemplate.objects.get(name='Power Strike')
        self.assertEqual(skill.power_ratio, 1.2)
        self.assertEqual(
            list(skill.level_configs.values_list('skill_level', 'damage_multiplier', 'required_materials')),
            [(1, 1.0, []), (2, 1.5, [{'item_template_id': stone.pk, 'quantity': 3}])],
        )

    def test_skill_level_rules_still_apply(self):
        stone = ItemTemplate.objects.create(name='Skill Stone', item_type='etc')
        levels = [{
            'skill_level': 1, 'required_char_level': 1, 'damage_multiplier': 100, 'final_damage_bonus': '',
            'required_materials': f'[{{"item_template_id": {stone.pk}, "quantity": 1}}]',
        }]

        response = self.client.post(reverse('studio:skill-new'), self.skill_data(levels))

        self.assertEqual(response.status_code, 200)  # level 1 must unlock automatically
        self.assertFalse(SkillLevelConfig.objects.exists())

    def test_effect_percentages_are_stored_as_fractions(self):
        fields = {
            name: 0 for name in (
                'flat_hp_change', 'flat_mp_change', 'flat_att_change', 'flat_str_change', 'flat_agi_change',
                'flat_int_change', 'hp_change_per_turn', 'mp_change_per_turn', 'exp_rate_change',
                'lumis_rate_change', 'drop_rate_change', 'shields_points', 'cooldown_reduction', 'dispel_count',
            )
        }
        response = self.client.post(reverse('studio:effect-new'), {
            **fields, 'name': 'War Cry', 'effect_kind': 'BUFF', 'duration_turns': 3, 'stacking_rule': 'REFRESH',
            'dispellable': 'on', 'percent_att_change': 20, 'final_damage_modifier': 10, 'description': '',
        })

        effect = EffectTemplate.objects.get(name='War Cry')
        self.assertRedirects(response, reverse('studio:effect-edit', args=[effect.pk]))
        self.assertEqual((effect.percent_att_change, effect.final_damage_modifier, effect.percent_str_change), (0.2, 0.1, 0))


class WorldEditorTests(StudioTestCase):
    def enemy(self, name='Slime'):
        return EnemyTemplate.objects.create(
            name=name, level=1, base_hp=10, base_mp=0, base_att=1, exp_reward=1, lumis_reward_min=0, lumis_reward_max=1,
        )

    def test_enemy_with_loot(self):
        jelly = ItemTemplate.objects.create(name='Jelly', item_type='etc')
        data = {
            'name': 'Blue Snail', 'level': 3, 'base_hp': 40, 'base_mp': 0, 'base_att': 4,
            'exp_reward': 5, 'lumis_reward_min': 1, 'lumis_reward_max': 4,
            **formset_data('skills', []),
            **formset_data('loot', [{
                'item_template': jelly.pk, 'base_drop_rate': 25, 'min_quantity': 1, 'max_quantity': 2, 'drop_type': 'common',
            }]),
        }

        self.client.post(reverse('studio:enemy-new'), data)

        loot = LootTable.objects.get(enemy__name='Blue Snail')
        self.assertEqual((loot.item_template, loot.base_drop_rate, loot.max_quantity), (jelly, 0.25, 2))

    def test_enemy_ranges_must_be_in_order(self):
        jelly = ItemTemplate.objects.create(name='Jelly', item_type='etc')
        response = self.client.post(reverse('studio:enemy-new'), {
            'name': 'Bad Snail', 'level': 3, 'base_hp': 40, 'base_mp': 0, 'base_att': 4,
            'exp_reward': 5, 'lumis_reward_min': 9, 'lumis_reward_max': 4,
            **formset_data('skills', []),
            **formset_data('loot', [{
                'item_template': jelly.pk, 'base_drop_rate': 25, 'min_quantity': 3, 'max_quantity': 2, 'drop_type': 'common',
            }]),
        })

        self.assertIn('lumis_reward_max', response.context['form'].errors)
        self.assertIn('max_quantity', response.context['formsets']['loot'].forms[0].errors)
        self.assertFalse(EnemyTemplate.objects.filter(name='Bad Snail').exists())

    def dungeon_data(self, rows):
        return {
            'name': 'Snail Field', 'location': '', 'required_level': 1, 'stamina_cost': 10,
            'exp_reward': 0, 'lumis_reward': 0, 'description': '', **formset_data('enemies', rows),
        }

    def test_dungeon_holds_at_most_six_enemies(self):
        snail, slime = self.enemy('Snail'), self.enemy('Slime')

        too_many = self.client.post(reverse('studio:dungeon-new', args=['normal']), self.dungeon_data([
            {'enemy': snail.pk, 'count': 4}, {'enemy': slime.pk, 'count': 3},
        ]))
        self.assertEqual(too_many.status_code, 200)
        self.assertFalse(NormalDungeonTemplate.objects.exists())

        self.client.post(reverse('studio:dungeon-new', args=['normal']), self.dungeon_data([
            {'enemy': snail.pk, 'count': 4}, {'enemy': slime.pk, 'count': 2},
        ]))
        dungeon = NormalDungeonTemplate.objects.get()
        self.assertEqual(sorted(dungeon.stage_enemies.values_list('count', flat=True)), [2, 4])

    def test_region_with_locations(self):
        self.client.post(reverse('studio:region-new'), {
            'name': 'Victoria', 'order': 1, 'description': '',
            **formset_data('locations', [{'name': 'Henesys', 'order': 1, 'description': ''}]),
        })

        self.assertEqual(list(Region.objects.get(name='Victoria').locations.values_list('name', flat=True)), ['Henesys'])


class DashboardTests(StudioTestCase):
    def test_lists_configuration_problems(self):
        Job.objects.create(name='Wanderer', character_class=self.warrior)
        NormalDungeonTemplate.objects.create(name='Empty Cave')
        ItemTemplate.objects.create(name='Mystery Potion', item_type='use')

        checks = self.client.get(reverse('studio:dashboard')).context['checks']

        names = {name for check in checks for name in check['names']}
        self.assertTrue({'Wanderer', 'Empty Cave', 'Mystery Potion'} <= names)
