from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.battles.models import CombatInstance
from apps.characters.models import Character
from apps.inventory.models import InventoryItem
from apps.items.models import ItemTemplate
from apps.users.models import GameUser
from apps.world.models import EnemyTemplate, NormalDungeonTemplate, NormalStageEnemy

from .models import Party, PartyInvitation, PartyMember, PendingPartyLoot


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


class PendingLootOnDissolutionTests(APITestCase):
    """Undistributed party loot goes to the leader instead of vanishing."""

    def setUp(self):
        self.leader = GameUser.objects.create_user(
            username='loot-leader', email='loot-leader@example.com', password='test-pass-123'
        )
        self.leader.character = Character.objects.create(name='LootLeader')
        self.leader.save(update_fields=['character'])
        self.client.force_authenticate(self.leader)
        self.client.post(reverse('party-create-party'), {'name': 'Loot Crew'}, format='json')
        self.party = Party.objects.get(leader=self.leader.character)
        self.gem = ItemTemplate.objects.create(name='Party Gem', item_type='etc')
        PendingPartyLoot.objects.create(party=self.party, item_template=self.gem, quantity=3)

    def leader_gems(self):
        return sum(
            InventoryItem.objects.filter(owner=self.leader.character, template=self.gem)
            .values_list('quantity', flat=True)
        )

    def test_disbanding_hands_pending_loot_to_the_leader(self):
        response = self.client.delete(reverse('party-disband'))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(self.leader_gems(), 3)
        self.assertFalse(PendingPartyLoot.objects.exists())

    def test_last_member_leaving_hands_pending_loot_to_them(self):
        self.client.post(reverse('party-leave'))

        self.assertEqual(self.leader_gems(), 3)
        self.assertFalse(Party.objects.filter(pk=self.party.pk).exists())

    def test_leaving_a_solo_party_hands_over_its_pending_loot(self):
        self.party.is_solo = True
        self.party.max_size = 1
        self.party.save(update_fields=['is_solo', 'max_size'])

        response = self.client.post(reverse('party-create-party'), {'name': 'Next'}, format='json')

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(self.leader_gems(), 3)


class PartyInvitationExpiryTests(TestCase):
    def test_invitations_last_one_hour(self):
        leader = Character.objects.create(name='Inviter')
        guest = Character.objects.create(name='Guest')
        party = Party.objects.create(name='Timed', leader=leader)

        invitation = PartyInvitation.objects.create(party=party, sender=leader, receiver=guest)

        lifetime = invitation.expires_at - invitation.created_at
        self.assertAlmostEqual(lifetime.total_seconds(), 3600, delta=5)
