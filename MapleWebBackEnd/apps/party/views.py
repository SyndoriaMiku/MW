from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated

from .models import Party, PartyMember, PendingPartyLoot
from apps.characters.models import Character
from apps.inventory.models import InventoryItem

class PartyViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated]

    @action(detail=False, methods=['post'])
    def distribute_loot(self, request):
        """
        API for Party Leader to distribute a PendingPartyLoot to a party member.
        Required data:
        - loot_id: ID of the PendingPartyLoot
        - character_id: ID of the Character to receive the loot
        """
        game_user = request.user
        character = getattr(game_user, 'character', None)
        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_400_BAD_REQUEST)

        loot_id = request.data.get('loot_id')
        target_char_id = request.data.get('character_id')

        if not loot_id or not target_char_id:
            return Response({"detail": "Missing loot_id or character_id."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            loot = PendingPartyLoot.objects.get(id=loot_id)
        except PendingPartyLoot.DoesNotExist:
            return Response({"detail": "Loot not found."}, status=status.HTTP_404_NOT_FOUND)

        party = loot.party

        # Check if caller is party leader
        if party.leader != character:
            return Response({"detail": "Only the Party Leader can distribute loot."}, status=status.HTTP_403_FORBIDDEN)

        # Check if target character is in the party
        if not PartyMember.objects.filter(party=party, character_id=target_char_id).exists() and party.leader.id != target_char_id:
            return Response({"detail": "Target character is not in the party."}, status=status.HTTP_400_BAD_REQUEST)

        # Distribute loot
        target_char = Character.objects.get(id=target_char_id)
        template = loot.item_template

        if template.item_type in ['equipment']:
            # Create separate equipment
            for _ in range(loot.quantity):
                InventoryItem.objects.create(
                    template=template,
                    owner=target_char,
                    quantity=1
                )
        else:
            # Stackable
            inv_item, created = InventoryItem.objects.get_or_create(
                template=template,
                owner=target_char,
                is_destroyed=False,
                defaults={'quantity': 0}
            )
            inv_item.quantity += loot.quantity
            inv_item.save(update_fields=['quantity'])

        # Delete pending loot after distribution
        loot.delete()

        return Response({"detail": f"Loot distributed successfully to {target_char.name}."})
