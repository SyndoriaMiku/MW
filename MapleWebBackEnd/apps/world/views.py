from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from .models import NormalDungeonTemplate, BossDungeonTemplate, DungeonClearLog
from .serializers import NormalDungeonSerializer, BossDungeonSerializer
from apps.battles.models import CombatInstance, Combatant
from apps.battles.services import BattleService
from apps.party.models import Party, PartyMember
from apps.characters.models import Character


class NormalDungeonViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = NormalDungeonTemplate.objects.all()
    serializer_class = NormalDungeonSerializer
    permission_classes = [IsAuthenticated]

    @action(detail=True, methods=['post'])
    def enter(self, request, pk=None):
        """
        Enter a normal dungeon. Requires the user to have enough stamina.
        Must be solo (auto-creates a solo party if not already in one).
        (B-2 fix) Now uses BattleService to properly initialize combat.
        """
        dungeon = self.get_object()
        user = request.user
        character = getattr(user, 'character', None)
        
        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_400_BAD_REQUEST)

        # Level check
        if character.level < dungeon.required_level:
            return Response({"detail": f"Required level is {dungeon.required_level}."}, status=status.HTTP_400_BAD_REQUEST)

        # Validate encounter configuration before creating a party or charging
        # stamina.  A broken admin configuration must not cost the player.
        enemies = list(dungeon.stage_enemies.select_related('enemy').all())
        if not enemies:
            return Response({"detail": "No enemies configured for this dungeon."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            # Serialize entry attempts for the same character, then repeat all
            # mutable-state checks under the lock.
            character = Character.objects.select_for_update().get(pk=character.pk)
            character.update_stamina()
            if character.current_stamina < dungeon.stamina_cost:
                return Response({"detail": "Not enough stamina."}, status=status.HTTP_400_BAD_REQUEST)

            char_ct = ContentType.objects.get_for_model(character)
            if Combatant.objects.filter(
                content_type=char_ct,
                objects_id=str(character.id),
                combat_instance__status='in_progress'
            ).exists():
                return Response({"detail": "You are already in an active battle."}, status=status.HTTP_400_BAD_REQUEST)

            party_member = PartyMember.objects.filter(
                character=character
            ).select_related('party').first()
            if not party_member:
                party = Party.objects.create(
                    name=f"{character.name}'s Party", leader=character, max_size=1
                )
                PartyMember.objects.create(party=party, character=character, position=1)
            else:
                party = party_member.party
                if party.party_members.count() > 1:
                    return Response(
                        {"detail": "Normal dungeons must be challenged solo (party of 1)."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            character.current_stamina -= dungeon.stamina_cost
            character.save(update_fields=['current_stamina'])

            combat = BattleService.create_combat_instance(party, enemies)
            combat.normal_dungeon = dungeon
            BattleService.start_combat(combat)
            combat.save(update_fields=['normal_dungeon'])

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
        Enter a boss dungeon. Requires a party. Leader only.
        Checks max party size, level requirements, and clear cooldowns.
        (B-2 fix) Now uses BattleService to properly initialize combat.
        """
        dungeon = self.get_object()
        user = request.user
        character = getattr(user, 'character', None)

        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_400_BAD_REQUEST)

        party_member = PartyMember.objects.filter(character=character).select_related('party').first()
        if not party_member:
            return Response({"detail": "You must be in a party to enter a Boss Dungeon."}, status=status.HTTP_400_BAD_REQUEST)

        party = party_member.party
        if party.leader != character:
            return Response({"detail": "Only the Party Leader can start the Boss Dungeon."}, status=status.HTTP_403_FORBIDDEN)

        # Check if party already in combat
        if CombatInstance.objects.filter(party=party, status='in_progress').exists():
            return Response({"detail": "Party is already in an active battle."}, status=status.HTTP_400_BAD_REQUEST)

        members = list(party.party_members.select_related('character').all())
        if len(members) > dungeon.max_party_size:
            return Response({"detail": f"Party size exceeds max size ({dungeon.max_party_size}) for this dungeon."}, status=status.HTTP_400_BAD_REQUEST)

        # Level & cooldown checks per member
        now = timezone.now()
        char_ct = ContentType.objects.get_for_model(character)
        for pm in members:
            c = pm.character

            # Level check
            if c.level < dungeon.required_level:
                return Response({"detail": f"Member {c.name} does not meet the level requirement ({dungeon.required_level})."}, status=status.HTTP_400_BAD_REQUEST)

            # (LG-1) Check not already in another battle
            if Combatant.objects.filter(
                content_type=char_ct,
                objects_id=str(c.id),
                combat_instance__status='in_progress'
            ).exists():
                return Response({"detail": f"Member {c.name} is already in another active battle."}, status=status.HTTP_400_BAD_REQUEST)

            # Check clear cooldown
            last_clear = DungeonClearLog.objects.filter(character=c, dungeon=dungeon).order_by('-cleared_at').first()
            if last_clear:
                cleared_at = last_clear.cleared_at
                is_cooldown = False
                if dungeon.time_type == BossDungeonTemplate.TimeType.DAILY:
                    is_cooldown = (now - cleared_at).total_seconds() < 86400
                elif dungeon.time_type == BossDungeonTemplate.TimeType.WEEKLY:
                    is_cooldown = (now - cleared_at).days < 7
                elif dungeon.time_type == BossDungeonTemplate.TimeType.MONTHLY:
                    is_cooldown = (now - cleared_at).days < 30
                
                if is_cooldown:
                    return Response({"detail": f"Member {c.name} has already cleared this {dungeon.time_type} dungeon."}, status=status.HTTP_400_BAD_REQUEST)

        # Get enemies from dungeon
        enemies = list(dungeon.stage_enemies.select_related('enemy').all())
        if not enemies:
            return Response({"detail": "No enemies configured for this dungeon."}, status=status.HTTP_400_BAD_REQUEST)

        # (B-2 fix) Use BattleService to properly create and initialize combat
        with transaction.atomic():
            combat = BattleService.create_combat_instance(party, enemies)
            combat.boss_dungeon = dungeon
            BattleService.start_combat(combat)
            combat.save()

        return Response({
            "detail": "Entered boss dungeon.",
            "combat_instance_id": combat.id
        })
