from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from .models import Party, PartyMember, PartyInvitation, PendingPartyLoot
from .serializers import (
    PartySerializer, PartyInvitationSerializer, PendingPartyLootSerializer
)
from apps.characters.models import Character
from apps.inventory.models import InventoryItem


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _get_character(request):
    """Return the character attached to request.user, or None."""
    return getattr(request.user, 'character', None)


def _character_in_active_battle(character):
    """
    Return the active CombatInstance if character is currently in one, else None.
    Used to guard against leave/kick/disband during combat.
    """
    from django.contrib.contenttypes.models import ContentType
    from apps.battles.models import Combatant
    ct = ContentType.objects.get_for_model(character)
    combatant = Combatant.objects.filter(
        content_type=ct,
        objects_id=str(character.id),
        combat_instance__status='in_progress'
    ).select_related('combat_instance').first()
    return combatant.combat_instance if combatant else None


def _next_free_position(party):
    """Return the lowest unused position slot (1–4) in a party."""
    used = set(party.party_members.values_list('position', flat=True))
    for pos in range(1, party.max_size + 1):
        if pos not in used:
            return pos
    return None


# ---------------------------------------------------------------------------
# ViewSet
# ---------------------------------------------------------------------------

class PartyViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]

    # ------------------------------------------------------------------
    # 1. CREATE
    # ------------------------------------------------------------------
    @action(detail=False, methods=['post'])
    def create_party(self, request):
        """
        POST /api/party/party/create_party/
        Create a new party. The caller becomes the leader.
        Body: { "name": "Party Name" }
        Rules:
        - Character must not already be in a party.
        - max_size is fixed at 4.
        """
        character = _get_character(request)
        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_400_BAD_REQUEST)

        # Prevent joining two parties
        if PartyMember.objects.filter(character=character).exists():
            return Response({"detail": "You are already in a party. Leave first."}, status=status.HTTP_400_BAD_REQUEST)

        name = request.data.get('name', '').strip()
        if not name:
            name = f"{character.name}'s Party"

        with transaction.atomic():
            party = Party.objects.create(
                name=name,
                leader=character,
                max_size=4,
            )
            PartyMember.objects.create(party=party, character=character, position=1)

        return Response(PartySerializer(party).data, status=status.HTTP_201_CREATED)

    # ------------------------------------------------------------------
    # 2. MY PARTY (info)
    # ------------------------------------------------------------------
    @action(detail=False, methods=['get'])
    def my(self, request):
        """
        GET /api/party/party/my/
        Return the current party of the authenticated character.
        """
        character = _get_character(request)
        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_400_BAD_REQUEST)

        membership = PartyMember.objects.filter(character=character).select_related('party').first()
        if not membership:
            return Response({"detail": "You are not in a party."}, status=status.HTTP_404_NOT_FOUND)

        party = Party.objects.prefetch_related(
            'party_members__character', 'pending_loots'
        ).get(pk=membership.party_id)

        return Response(PartySerializer(party).data)

    # ------------------------------------------------------------------
    # 3. DISBAND
    # ------------------------------------------------------------------
    @action(detail=False, methods=['delete'])
    def disband(self, request):
        """
        DELETE /api/party/party/disband/
        Disband the party. Leader only. Blocked during combat.
        """
        character = _get_character(request)
        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_400_BAD_REQUEST)

        membership = PartyMember.objects.filter(character=character).select_related('party').first()
        if not membership:
            return Response({"detail": "You are not in a party."}, status=status.HTTP_400_BAD_REQUEST)

        party = membership.party
        if party.leader != character:
            return Response({"detail": "Only the party leader can disband the party."}, status=status.HTTP_403_FORBIDDEN)

        # Guard: cannot disband during combat
        if _character_in_active_battle(character):
            return Response({"detail": "Cannot disband the party while in an active battle."}, status=status.HTTP_400_BAD_REQUEST)

        party.delete()  # CASCADE removes PartyMember and PartyInvitation rows
        return Response({"detail": "Party has been disbanded."})

    # ------------------------------------------------------------------
    # 4. LEAVE
    # ------------------------------------------------------------------
    @action(detail=False, methods=['post'])
    def leave(self, request):
        """
        POST /api/party/party/leave/
        Leave the current party. Blocked during combat.
        If the leader leaves, the next member (by position) is promoted automatically.
        """
        character = _get_character(request)
        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_400_BAD_REQUEST)

        membership = PartyMember.objects.filter(character=character).select_related('party').first()
        if not membership:
            return Response({"detail": "You are not in a party."}, status=status.HTTP_400_BAD_REQUEST)

        party = membership.party

        if _character_in_active_battle(character):
            return Response({"detail": "Cannot leave the party while in an active battle."}, status=status.HTTP_400_BAD_REQUEST)

        is_leader = (party.leader_id == character.id)

        with transaction.atomic():
            membership.delete()

            if is_leader:
                next_member = PartyMember.objects.filter(party=party).order_by('position').first()
                if next_member:
                    party.leader = next_member.character
                    party.save(update_fields=['leader'])
                else:
                    party.delete()

        return Response({"detail": "You have left the party."})

    # ------------------------------------------------------------------
    # 5. KICK
    # ------------------------------------------------------------------
    @action(detail=True, methods=['post'])
    def kick(self, request, pk=None):
        """
        POST /api/party/party/{id}/kick/
        Kick a member from the party. Leader only. Blocked during combat.
        Body: { "character_id": "<id>" }
        """
        character = _get_character(request)
        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            party = Party.objects.get(pk=pk)
        except Party.DoesNotExist:
            return Response({"detail": "Party not found."}, status=status.HTTP_404_NOT_FOUND)

        if party.leader_id != character.id:
            return Response({"detail": "Only the party leader can kick members."}, status=status.HTTP_403_FORBIDDEN)

        if _character_in_active_battle(character):
            return Response({"detail": "Cannot kick a member while in an active battle."}, status=status.HTTP_400_BAD_REQUEST)

        target_char_id = request.data.get('character_id')
        if not target_char_id:
            return Response({"detail": "character_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        if str(target_char_id) == str(character.id):
            return Response({"detail": "You cannot kick yourself. Use leave instead."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            membership = PartyMember.objects.get(party=party, character_id=target_char_id)
        except PartyMember.DoesNotExist:
            return Response({"detail": "This character is not in your party."}, status=status.HTTP_404_NOT_FOUND)

        membership.delete()
        return Response({"detail": "Member has been kicked from the party."})

    # ------------------------------------------------------------------
    # 6. TRANSFER LEADER
    # ------------------------------------------------------------------
    @action(detail=False, methods=['post'])
    def transfer_leader(self, request):
        """
        POST /api/party/party/transfer_leader/
        Transfer leadership to another party member.
        Body: { "character_id": "<id>" }
        """
        character = _get_character(request)
        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_400_BAD_REQUEST)

        membership = PartyMember.objects.filter(character=character).select_related('party').first()
        if not membership:
            return Response({"detail": "You are not in a party."}, status=status.HTTP_400_BAD_REQUEST)

        party = membership.party
        if party.leader_id != character.id:
            return Response({"detail": "Only the current leader can transfer leadership."}, status=status.HTTP_403_FORBIDDEN)

        target_char_id = request.data.get('character_id')
        if not target_char_id or str(target_char_id) == str(character.id):
            return Response({"detail": "Provide a different character_id to transfer leadership to."}, status=status.HTTP_400_BAD_REQUEST)

        if not PartyMember.objects.filter(party=party, character_id=target_char_id).exists():
            return Response({"detail": "Target character is not in your party."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            new_leader = Character.objects.get(pk=target_char_id)
        except Character.DoesNotExist:
            return Response({"detail": "Character not found."}, status=status.HTTP_404_NOT_FOUND)

        party.leader = new_leader
        party.save(update_fields=['leader'])
        return Response({"detail": f"Leadership transferred to {new_leader.name}."})

    # ------------------------------------------------------------------
    # 7. INVITE
    # ------------------------------------------------------------------
    @action(detail=False, methods=['post'])
    def invite(self, request):
        """
        POST /api/party/party/invite/
        Invite a character to the party. Leader only.
        Body: { "character_id": "<id>" }
        Rules:
        - Party must not be full.
        - Target must not be in any party already.
        - No duplicate pending invitation from this party to this character.
        - Cannot invite while in combat.
        """
        character = _get_character(request)
        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_400_BAD_REQUEST)

        membership = PartyMember.objects.filter(character=character).select_related('party').first()
        if not membership:
            return Response({"detail": "You are not in a party."}, status=status.HTTP_400_BAD_REQUEST)

        party = membership.party
        if party.leader_id != character.id:
            return Response({"detail": "Only the party leader can invite members."}, status=status.HTTP_403_FORBIDDEN)

        if _character_in_active_battle(character):
            return Response({"detail": "Cannot invite while in an active battle."}, status=status.HTTP_400_BAD_REQUEST)

        if party.party_members.count() >= party.max_size:
            return Response({"detail": "The party is already full."}, status=status.HTTP_400_BAD_REQUEST)

        target_char_id = request.data.get('character_id')
        if not target_char_id:
            return Response({"detail": "character_id is required."}, status=status.HTTP_400_BAD_REQUEST)
        if str(target_char_id) == str(character.id):
            return Response({"detail": "You cannot invite yourself."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            target = Character.objects.get(pk=target_char_id)
        except Character.DoesNotExist:
            return Response({"detail": "Character not found."}, status=status.HTTP_404_NOT_FOUND)

        # Target must not already be in a party
        if PartyMember.objects.filter(character=target).exists():
            return Response({"detail": f"{target.name} is already in a party."}, status=status.HTTP_400_BAD_REQUEST)

        # No active (pending + not expired) invitation from this party
        now = timezone.now()
        if PartyInvitation.objects.filter(
            party=party,
            receiver=target,
            status=PartyInvitation.Status.PENDING,
            expires_at__gt=now
        ).exists():
            return Response({"detail": f"A pending invitation to {target.name} already exists."}, status=status.HTTP_400_BAD_REQUEST)

        invitation = PartyInvitation.objects.create(
            party=party,
            sender=character,
            receiver=target,
        )
        return Response(PartyInvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)

    # ------------------------------------------------------------------
    # 8. LIST INVITATIONS (received by the current character)
    # ------------------------------------------------------------------
    @action(detail=False, methods=['get'])
    def invitations(self, request):
        """
        GET /api/party/party/invitations/
        List all pending invitations received by the current character.
        """
        character = _get_character(request)
        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_400_BAD_REQUEST)

        now = timezone.now()
        # Auto-expire stale invitations
        PartyInvitation.objects.filter(
            receiver=character,
            status=PartyInvitation.Status.PENDING,
            expires_at__lte=now
        ).update(status=PartyInvitation.Status.EXPIRED)

        invitations = PartyInvitation.objects.filter(
            receiver=character,
            status=PartyInvitation.Status.PENDING,
        ).select_related('party', 'sender', 'receiver').order_by('-created_at')

        return Response(PartyInvitationSerializer(invitations, many=True).data)

    # ------------------------------------------------------------------
    # 9. ACCEPT INVITATION
    # ------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='accept')
    def accept_invitation(self, request, pk=None):
        """
        POST /api/party/party/{id}/accept/
        Accept a party invitation. pk = invitation id.
        """
        character = _get_character(request)
        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            invitation = PartyInvitation.objects.select_related('party').get(
                pk=pk, receiver=character
            )
        except PartyInvitation.DoesNotExist:
            return Response({"detail": "Invitation not found."}, status=status.HTTP_404_NOT_FOUND)

        now = timezone.now()
        if invitation.status != PartyInvitation.Status.PENDING or invitation.expires_at <= now:
            invitation.status = PartyInvitation.Status.EXPIRED
            invitation.save(update_fields=['status'])
            return Response({"detail": "This invitation has expired or is no longer valid."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Lock the party row to safely check size
            party = Party.objects.select_for_update().get(pk=invitation.party_id)

            # Re-check: character might have joined another party between invite and accept
            if PartyMember.objects.filter(character=character).exists():
                return Response({"detail": "You are already in a party."}, status=status.HTTP_400_BAD_REQUEST)

            # Re-check party not full
            current_count = party.party_members.count()
            if current_count >= party.max_size:
                return Response({"detail": "The party is now full."}, status=status.HTTP_400_BAD_REQUEST)

            position = _next_free_position(party)
            if position is None:
                return Response({"detail": "No available position in the party."}, status=status.HTTP_400_BAD_REQUEST)

            PartyMember.objects.create(party=party, character=character, position=position)
            invitation.status = PartyInvitation.Status.ACCEPTED
            invitation.save(update_fields=['status'])

        return Response({
            "detail": f"You have joined {party.name}.",
            "party_id": party.id,
            "position": position,
        })

    # ------------------------------------------------------------------
    # 10. DECLINE INVITATION
    # ------------------------------------------------------------------
    @action(detail=True, methods=['post'], url_path='decline')
    def decline_invitation(self, request, pk=None):
        """
        POST /api/party/party/{id}/decline/
        Decline a party invitation. pk = invitation id.
        """
        character = _get_character(request)
        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            invitation = PartyInvitation.objects.get(
                pk=pk, receiver=character, status=PartyInvitation.Status.PENDING
            )
        except PartyInvitation.DoesNotExist:
            return Response({"detail": "Invitation not found or already processed."}, status=status.HTTP_404_NOT_FOUND)

        invitation.status = PartyInvitation.Status.DECLINED
        invitation.save(update_fields=['status'])
        return Response({"detail": "Invitation declined."})

    # ------------------------------------------------------------------
    # 11. PENDING LOOT LIST
    # ------------------------------------------------------------------
    @action(detail=False, methods=['get'])
    def loot(self, request):
        """
        GET /api/party/party/loot/
        View all pending party loot waiting to be distributed.
        """
        character = _get_character(request)
        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_400_BAD_REQUEST)

        membership = PartyMember.objects.filter(character=character).select_related('party').first()
        if not membership:
            return Response({"detail": "You are not in a party."}, status=status.HTTP_400_BAD_REQUEST)

        loots = PendingPartyLoot.objects.filter(
            party=membership.party
        ).select_related('item_template')

        return Response(PendingPartyLootSerializer(loots, many=True).data)

    # ------------------------------------------------------------------
    # 12. DISTRIBUTE LOOT
    # ------------------------------------------------------------------
    @action(detail=False, methods=['post'])
    def distribute_loot(self, request):
        """
        POST /api/party/party/distribute_loot/
        Distribute a pending party loot item to a specific member.
        Body: { "loot_id": <int>, "character_id": "<id>" }
        Leader only.
        """
        character = _get_character(request)
        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_400_BAD_REQUEST)

        loot_id = request.data.get('loot_id')
        target_char_id = request.data.get('character_id')
        if not loot_id or not target_char_id:
            return Response({"detail": "Both loot_id and character_id are required."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            loot = PendingPartyLoot.objects.select_related('party', 'item_template').get(pk=loot_id)
        except PendingPartyLoot.DoesNotExist:
            return Response({"detail": "Loot not found."}, status=status.HTTP_404_NOT_FOUND)

        party = loot.party
        if party.leader_id != character.id:
            return Response({"detail": "Only the party leader can distribute loot."}, status=status.HTTP_403_FORBIDDEN)

        is_member = (
            PartyMember.objects.filter(party=party, character_id=target_char_id).exists()
            or str(party.leader_id) == str(target_char_id)
        )
        if not is_member:
            return Response({"detail": "Target character is not in the party."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            target_char = Character.objects.get(pk=target_char_id)
        except Character.DoesNotExist:
            return Response({"detail": "Character not found."}, status=status.HTTP_404_NOT_FOUND)

        with transaction.atomic():
            try:
                loot = PendingPartyLoot.objects.select_for_update().select_related(
                    'party', 'item_template'
                ).get(pk=loot_id)
            except PendingPartyLoot.DoesNotExist:
                return Response(
                    {"detail": "Loot has already been distributed."},
                    status=status.HTTP_409_CONFLICT,
                )

            party = loot.party
            if party.leader_id != character.id:
                return Response(
                    {"detail": "Only the party leader can distribute loot."},
                    status=status.HTTP_403_FORBIDDEN,
                )
            if not PartyMember.objects.filter(
                party=party, character_id=target_char_id
            ).exists():
                return Response(
                    {"detail": "Target character is no longer in the party."},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            template = loot.item_template
            if not template.is_stackable:
                for _ in range(loot.quantity):
                    InventoryItem.objects.create(template=template, owner=target_char, quantity=1)
            else:
                inv_item, created = InventoryItem.objects.get_or_create(
                    template=template,
                    owner=target_char,
                    is_destroyed=False,
                    defaults={'quantity': loot.quantity}
                )
                if not created:
                    InventoryItem.objects.filter(pk=inv_item.pk).update(
                        quantity=F('quantity') + loot.quantity
                    )
            loot.delete()

        return Response({"detail": f"Loot distributed to {target_char.name}."})
