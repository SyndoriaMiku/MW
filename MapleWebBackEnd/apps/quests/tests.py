from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from apps.characters.models import Character
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
