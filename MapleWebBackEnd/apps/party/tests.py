from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.battles.models import CombatInstance
from apps.characters.models import Character
from apps.users.models import GameUser
from apps.world.models import EnemyTemplate, NormalDungeonTemplate, NormalStageEnemy

from .models import Party, PartyMember


class MalformedPartyInputTests(APITestCase):
    def setUp(self):
        self.user = GameUser.objects.create_user(
            username='party-bad-input', email='party-bad@example.com', password='test-pass-123'
        )
        self.user.character = Character.objects.create(name='PartyBadInput')
        self.user.save(update_fields=['character'])
        self.client.force_authenticate(self.user)

    def test_distribute_loot_rejects_non_integer_loot_id(self):
        response = self.client.post(
            reverse('party-distribute-loot'),
            {'loot_id': 'abc', 'character_id': self.user.character.id}, format='json',
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_non_string_party_name_is_accepted_as_text(self):
        response = self.client.post(reverse('party-create-party'), {'name': 123}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['name'], '123')


class SoloDungeonPartyTests(APITestCase):
    """The party auto-created for a solo normal dungeon must not trap the player."""

    def create_player(self, name):
        user = GameUser.objects.create_user(
            username=name, email=f'{name}@example.com', password='test-pass-123'
        )
        user.character = Character.objects.create(name=name)
        user.save(update_fields=['character'])
        return user

    def setUp(self):
        self.user = self.create_player('solo-runner')
        enemy = EnemyTemplate.objects.create(
            name='Solo Slime', level=1, base_hp=1, base_mp=0, base_att=0,
            exp_reward=0, lumis_reward_min=0, lumis_reward_max=0,
        )
        dungeon = NormalDungeonTemplate.objects.create(name='Solo Field', stamina_cost=1)
        NormalStageEnemy.objects.create(stage=dungeon, enemy=enemy)
        self.client.force_authenticate(self.user)
        entered = self.client.post(reverse('normal-dungeon-enter', args=[dungeon.pk]))
        combat = CombatInstance.objects.get(pk=entered.data['combat_instance_id'])
        target = combat.combatants.get(is_player=False)
        self.client.post(
            reverse('battles:player-action', args=[combat.id]),
            {'action_type': 'ATTACK', 'target_id': target.id}, format='json',
        )
        self.solo_party = Party.objects.get(leader=self.user.character)
        self.assertTrue(self.solo_party.is_solo)

    def test_player_can_create_a_real_party_afterwards(self):
        response = self.client.post(reverse('party-create-party'), {'name': 'Real'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data['max_size'], 4)
        self.assertFalse(PartyMember.objects.filter(party=self.solo_party).exists())
        self.assertTrue(CombatInstance.objects.filter(party=self.solo_party).exists())

    def test_player_can_be_invited_and_join_another_party(self):
        leader = self.create_player('real-leader')
        self.client.force_authenticate(leader)
        self.client.post(reverse('party-create-party'), {'name': 'Crew'}, format='json')
        invite = self.client.post(
            reverse('party-invite'), {'character_id': self.user.character.id}, format='json'
        )
        self.assertEqual(invite.status_code, status.HTTP_201_CREATED)

        self.client.force_authenticate(self.user)
        accepted = self.client.post(reverse('party-accept-invitation', args=[invite.data['id']]))

        self.assertEqual(accepted.status_code, status.HTTP_200_OK)
        self.assertEqual(
            PartyMember.objects.get(character=self.user.character).party.name, 'Crew'
        )
