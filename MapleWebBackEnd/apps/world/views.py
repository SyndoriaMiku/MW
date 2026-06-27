from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
from datetime import timedelta

from .models import NormalDungeonTemplate, BossDungeonTemplate, DungeonClearLog
from .serializers import NormalDungeonSerializer, BossDungeonSerializer
from apps.battles.models import CombatInstance, Combatant
from apps.party.models import Party, PartyMember

class NormalDungeonViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NormalDungeonTemplate.objects.all()
    serializer_class = NormalDungeonSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['post'])
    def enter(self, request, pk=None):
        """
        Enter a normal dungeon. Requires the user to have enough stamina.
        Must be in a solo party (auto-creates one if not in a party).
        """
        dungeon = self.get_object()
        user = request.user
        character = getattr(user, 'character', None)
        
        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_400_BAD_REQUEST)

        # Level check
        if character.level < dungeon.required_level:
            return Response({"detail": f"Required level is {dungeon.required_level}."}, status=status.HTTP_400_BAD_REQUEST)

        # Stamina check
        character.update_stamina()
        if character.current_stamina < dungeon.stamina_cost:
            return Response({"detail": "Not enough stamina."}, status=status.HTTP_400_BAD_REQUEST)

        # Party check - Must be a party of 1
        party_member = PartyMember.objects.filter(character=character).first()
        if not party_member:
            # Auto-create party
            party = Party.objects.create(name=f"{character.name}'s Party", leader=character, max_size=1)
            PartyMember.objects.create(party=party, character=character, position=1)
        else:
            party = party_member.party
            if party.party_members.count() > 1:
                return Response({"detail": "Normal dungeons must be challenged solo (Party of 1)."}, status=status.HTTP_400_BAD_REQUEST)

        # Create CombatInstance
        combat = CombatInstance.objects.create(
            party=party,
            normal_dungeon=dungeon
        )

        # Add player to combat
        Combatant.objects.create(
            combat_instance=combat,
            content_type=character.get_content_type(),
            object_id=character.id,
            is_player=True,
            position=1,
            current_hp=character.total_hp,
            current_mp=character.total_mp
        )

        # Add enemies
        pos = 1
        for enemy_tpl in dungeon.enemies.all():
            Combatant.objects.create(
                combat_instance=combat,
                content_type=enemy_tpl.get_content_type(),
                object_id=enemy_tpl.id,
                is_player=False,
                position=pos,
                current_hp=enemy_tpl.base_hp,
                current_mp=enemy_tpl.base_mp
            )
            pos += 1

        return Response({
            "detail": "Entered normal dungeon.",
            "combat_instance_id": combat.id
        })


class BossDungeonViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = BossDungeonTemplate.objects.all()
    serializer_class = BossDungeonSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['post'])
    def enter(self, request, pk=None):
        """
        Enter a boss dungeon. Requires a party.
        Checks max party size and clear cooldowns (daily/weekly/monthly).
        """
        dungeon = self.get_object()
        user = request.user
        character = getattr(user, 'character', None)

        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_400_BAD_REQUEST)

        party_member = PartyMember.objects.filter(character=character).first()
        if not party_member:
            return Response({"detail": "You must be in a party to enter a Boss Dungeon."}, status=status.HTTP_400_BAD_REQUEST)

        party = party_member.party
        if party.leader != character:
            return Response({"detail": "Only the Party Leader can start the Boss Dungeon."}, status=status.HTTP_403_FORBIDDEN)

        members = party.party_members.all()
        if members.count() > dungeon.max_party_size:
            return Response({"detail": f"Party size exceeds max size ({dungeon.max_party_size}) for this dungeon."}, status=status.HTTP_400_BAD_REQUEST)

        # Cooldown & Level check
        now = timezone.now()
        for pm in members:
            c = pm.character
            if c.level < dungeon.required_level:
                return Response({"detail": f"Member {c.name} does not meet the level requirement ({dungeon.required_level})."}, status=status.HTTP_400_BAD_REQUEST)
            
            # Check Clear Log
            last_clear = DungeonClearLog.objects.filter(character=c, dungeon=dungeon).first()
            if last_clear:
                cleared_at = last_clear.cleared_at
                is_cooldown = False
                if dungeon.time_type == BossDungeonTemplate.TimeType.DAILY:
                    is_cooldown = (now - cleared_at).days < 1
                elif dungeon.time_type == BossDungeonTemplate.TimeType.WEEKLY:
                    is_cooldown = (now - cleared_at).days < 7
                elif dungeon.time_type == BossDungeonTemplate.TimeType.MONTHLY:
                    is_cooldown = (now - cleared_at).days < 30
                
                if is_cooldown:
                    return Response({"detail": f"Member {c.name} has already cleared this {dungeon.time_type}."}, status=status.HTTP_400_BAD_REQUEST)

        # Create CombatInstance
        combat = CombatInstance.objects.create(
            party=party,
            boss_dungeon=dungeon
        )

        # Add players
        for pm in members:
            c = pm.character
            Combatant.objects.create(
                combat_instance=combat,
                content_type=c.get_content_type(),
                object_id=c.id,
                is_player=True,
                position=pm.position,
                current_hp=c.total_hp,
                current_mp=c.total_mp
            )

        # Add boss
        pos = 1
        for enemy_tpl in dungeon.enemies.all():
            Combatant.objects.create(
                combat_instance=combat,
                content_type=enemy_tpl.get_content_type(),
                object_id=enemy_tpl.id,
                is_player=False,
                position=pos,
                current_hp=enemy_tpl.base_hp,
                current_mp=enemy_tpl.base_mp
            )
            pos += 1

        return Response({
            "detail": "Entered boss dungeon.",
            "combat_instance_id": combat.id
        })
