from datetime import timedelta

from django.core.exceptions import ValidationError
from django.test import TestCase
from django.utils import timezone

from apps.characters.models import Character
from apps.inventory.grant_service import grant_item
from apps.inventory.models import InventoryItem
from apps.items.models import ItemTemplate
from apps.world.models import EnemyTemplate

from .models import CharacterQuest, QuestObjective, QuestTemplate
from .services import QuestService


class QuestProvisioningTests(TestCase):
    def setUp(self):
        self.character = Character.objects.create(name='Quester')
        self.enemy = EnemyTemplate.objects.create(
            name='Quest Slime', level=1, base_hp=1, base_mp=0, base_att=0,
            exp_reward=0, lumis_reward_min=0, lumis_reward_max=0,
        )

    def quest(self, name, quest_type='once', *, objective=True, **fields):
        template = QuestTemplate.objects.create(
            name=name, description='', quest_type=quest_type, **fields
        )
        if objective:
            QuestObjective.objects.create(quest=template, enemy_to_defeat=self.enemy, defeat_count=1)
        return template

    def active_names(self):
        return set(
            QuestService.get_active_quests(self.character).values_list('quest__name', flat=True)
        )

    def status_of(self, template):
        return CharacterQuest.objects.get(character=self.character, quest=template).status

    def test_one_time_quests_are_provisioned(self):
        self.quest('Story 1')

        self.assertEqual(self.active_names(), {'Story 1'})

    def test_level_requirement_gates_every_quest_type(self):
        self.quest('Late story', required_level=5)
        self.quest('Late daily', 'daily', required_level=5)

        self.assertEqual(self.active_names(), set())
        self.character.level = 5
        self.character.save(update_fields=['level'])
        self.assertEqual(self.active_names(), {'Late story', 'Late daily'})

    def test_prerequisites_must_be_claimed_first(self):
        first = self.quest('Chapter 1')
        second = self.quest('Chapter 2')
        second.prerequisite_quests.add(first)

        self.assertEqual(self.active_names(), {'Chapter 1'})
        QuestService.update_progress(self.character, 'DEFEAT_ENEMY', enemy_id=self.enemy.id)
        QuestService.claim_reward(self.character, first.id)
        self.assertEqual(self.active_names(), {'Chapter 1', 'Chapter 2'})

    def test_quest_without_objectives_is_immediately_claimable(self):
        greeting = self.quest('Say hello', objective=False)

        self.active_names()

        self.assertEqual(self.status_of(greeting), CharacterQuest.Status.COMPLETED)
        self.assertTrue(QuestService.claim_reward(self.character, greeting.id)['success'])

    def test_one_time_quests_never_reset(self):
        story = self.quest('Story once')
        self.active_names()
        QuestService.update_progress(self.character, 'DEFEAT_ENEMY', enemy_id=self.enemy.id)
        QuestService.claim_reward(self.character, story.id)
        CharacterQuest.objects.filter(quest=story).update(
            last_reset_at=timezone.now() - timedelta(days=60)
        )

        self.active_names()

        self.assertEqual(self.status_of(story), CharacterQuest.Status.CLAIMED)

    def test_objective_added_later_reaches_existing_quests(self):
        story = self.quest('Growing story')
        self.active_names()
        QuestObjective.objects.create(quest=story, enemy_to_defeat=self.enemy, defeat_count=2)

        self.active_names()

        cq = CharacterQuest.objects.get(character=self.character, quest=story)
        self.assertEqual(cq.objective_progress.count(), 2)


class CollectItemObjectiveTests(TestCase):
    """COLLECT_ITEM progress is what the character holds now; claiming hands the items in."""

    def setUp(self):
        self.character = Character.objects.create(name='Collector')
        self.herb = ItemTemplate.objects.create(name='Herb', item_type='etc')
        self.quest = QuestTemplate.objects.create(name='Herbalist', description='', exp_reward=5)
        QuestObjective.objects.create(quest=self.quest, item_to_collect=self.herb, collect_count=5)

    def progress(self):
        QuestService.get_active_quests(self.character)
        cq = CharacterQuest.objects.get(character=self.character, quest=self.quest)
        objective = cq.objective_progress.get()
        return objective.current_count, cq.status

    def held(self):
        return sum(
            InventoryItem.objects.filter(owner=self.character, template=self.herb)
            .values_list('quantity', flat=True)
        )

    def test_items_from_any_source_count(self):
        grant_item(self.character, self.herb, 3)
        self.assertEqual(self.progress(), (3, CharacterQuest.Status.IN_PROGRESS))

        grant_item(self.character, self.herb, 4)
        self.assertEqual(self.progress(), (5, CharacterQuest.Status.COMPLETED))

    def test_destroyed_or_expired_stacks_do_not_count(self):
        InventoryItem.objects.create(owner=self.character, template=self.herb, quantity=5, is_destroyed=True)
        InventoryItem.objects.create(
            owner=self.character, template=self.herb, quantity=5,
            expired_at=timezone.now() - timedelta(seconds=1),
        )

        self.assertEqual(self.progress(), (0, CharacterQuest.Status.IN_PROGRESS))

    def test_losing_the_items_reopens_the_quest(self):
        grant_item(self.character, self.herb, 5)
        self.assertEqual(self.progress()[1], CharacterQuest.Status.COMPLETED)

        InventoryItem.objects.filter(owner=self.character, template=self.herb).update(quantity=2)

        self.assertEqual(self.progress(), (2, CharacterQuest.Status.IN_PROGRESS))

    def test_claiming_hands_the_items_in(self):
        grant_item(self.character, self.herb, 7)
        self.progress()

        result = QuestService.claim_reward(self.character, self.quest.id)

        self.assertTrue(result['success'])
        self.assertEqual(self.held(), 2)

    def test_claim_fails_when_the_items_are_gone(self):
        grant_item(self.character, self.herb, 5)
        self.progress()
        InventoryItem.objects.filter(owner=self.character, template=self.herb).delete()

        result = QuestService.claim_reward(self.character, self.quest.id)

        self.assertFalse(result['success'])
        self.character.refresh_from_db()
        self.assertEqual(self.character.current_exp, 0)
        self.assertEqual(self.status_of_quest(), CharacterQuest.Status.IN_PROGRESS)

    def status_of_quest(self):
        return CharacterQuest.objects.get(character=self.character, quest=self.quest).status


class QuestObjectiveValidationTests(TestCase):
    def setUp(self):
        self.quest = QuestTemplate.objects.create(name='Checked', description='')
        self.enemy = EnemyTemplate.objects.create(
            name='Check Slime', level=1, base_hp=1, base_mp=0, base_att=0,
            exp_reward=0, lumis_reward_min=0, lumis_reward_max=0,
        )
        self.herb = ItemTemplate.objects.create(name='Check Herb', item_type='etc')

    def objective(self, **fields):
        return QuestObjective(quest=self.quest, **fields)

    def test_single_type_objectives_are_valid(self):
        self.objective(enemy_to_defeat=self.enemy, defeat_count=3).full_clean()
        self.objective(defeat_count=3).full_clean()  # any enemy
        self.objective(item_to_collect=self.herb, collect_count=3).full_clean()
        self.objective(clear_count=1).full_clean()

    def test_mixed_types_are_rejected(self):
        with self.assertRaises(ValidationError):
            self.objective(defeat_count=3, item_to_collect=self.herb, collect_count=2).full_clean()

    def test_empty_objective_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.objective().full_clean()

    def test_target_without_a_count_is_rejected(self):
        with self.assertRaises(ValidationError):
            self.objective(enemy_to_defeat=self.enemy).full_clean()

    def test_collect_needs_an_item(self):
        with self.assertRaises(ValidationError):
            self.objective(collect_count=3).full_clean()
