from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.db.models import Prefetch
from django.utils import timezone
from django.contrib.contenttypes.models import ContentType

from .models import NormalDungeonTemplate, BossDungeonTemplate, DungeonClearLog, Location, Region
from .serializers import (
    BossDungeonSerializer, LocationSerializer, NormalDungeonSerializer, RegionSerializer,
)
from apps.battles.models import CombatInstance, Combatant
from apps.battles.services import BattleService
from apps.battles.serializers import CombatInstanceSerializer
from apps.party.models import Party, PartyMember
from apps.characters.models import Character
from apps.reset_cycles import period_start


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

            active_combat = BattleService.get_active_combat_for_character(character)
            if active_combat:
                return Response({
                    "detail": "You are already in an active battle. Resume it instead.",
                    "combat_instance_id": active_combat.id,
                    "combat": CombatInstanceSerializer(active_combat).data,
                }, status=status.HTTP_409_CONFLICT)

            party_member = PartyMember.objects.filter(
                character=character
            ).select_related('party').first()
            if not party_member:
                party = Party.objects.create(
                    name=f"{character.name}'s Party", leader=character, max_size=1, is_solo=True
                )
                PartyMember.objects.create(party=party, character=character, position=1)
            else:
                party = party_member.party
                if party.party_members.count() > 1:
                    return Response(
                        {"detail": "Normal dungeons must be challenged solo (party of 1)."},
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            combat = BattleService.create_combat_instance(party, enemies)
            combat.normal_dungeon = dungeon
            combat.stamina_cost_on_victory = dungeon.stamina_cost
            BattleService.start_combat(combat)
            combat.save(update_fields=['normal_dungeon', 'stamina_cost_on_victory'])

        return Response({
            "detail": "Entered normal dungeon.",
            "combat_instance_id": combat.id,
            "combat": CombatInstanceSerializer(combat).data,
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

        # Get enemies from dungeon
        enemies = list(dungeon.stage_enemies.select_related('enemy').all())
        if not enemies:
            return Response({"detail": "No enemies configured for this dungeon."}, status=status.HTTP_400_BAD_REQUEST)

        # (CRIT-09) Lock the party row before any mutable-state check so two
        # concurrent requests cannot both see "no active battle" and each
        # start one. Membership and leadership are re-read under the lock.
        with transaction.atomic():
            party_member = PartyMember.objects.filter(character=character).first()
            if not party_member:
                return Response({"detail": "You must be in a party to enter a Boss Dungeon."}, status=status.HTTP_400_BAD_REQUEST)

            party = Party.objects.select_for_update().get(pk=party_member.party_id)
            if party.leader_id != character.pk:
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
                    has_left=False,
                    combat_instance__status='in_progress'
                ).exists():
                    return Response({"detail": f"Member {c.name} is already in another active battle."}, status=status.HTTP_400_BAD_REQUEST)

                # Check clear cooldown
                cleared_this_period = DungeonClearLog.objects.filter(
                    character=c, dungeon=dungeon,
                    cleared_at__gte=period_start(dungeon.time_type, now),
                ).exists()
                if cleared_this_period:
                    return Response({"detail": f"Member {c.name} has already cleared this {dungeon.time_type} dungeon."}, status=status.HTTP_400_BAD_REQUEST)

            # (B-2 fix) Use BattleService to properly create and initialize combat
            combat = BattleService.create_combat_instance(party, enemies)
            combat.boss_dungeon = dungeon
            BattleService.start_combat(combat)
            combat.save()

        return Response({
            "detail": "Entered boss dungeon.",
            "combat_instance_id": combat.id
        })


def _locations_queryset():
    return Location.objects.select_related('region', 'normal_dungeon', 'boss_dungeon')


class WorldContextMixin:
    """Unpaginated world data, with the requesting character for access flags."""
    permission_classes = [IsAuthenticated]
    pagination_class = None

    def get_serializer_context(self):
        context = super().get_serializer_context()
        context['character'] = getattr(self.request.user, 'character', None)
        return context


class RegionViewSet(WorldContextMixin, viewsets.ReadOnlyModelViewSet):
    queryset = Region.objects.prefetch_related(
        Prefetch('locations', queryset=_locations_queryset().order_by('order'))
    )
    serializer_class = RegionSerializer


class LocationViewSet(WorldContextMixin, viewsets.ReadOnlyModelViewSet):
    queryset = _locations_queryset()
    serializer_class = LocationSerializer

    @action(detail=False, methods=['get'])
    def current(self, request):
        """The requesting character's current location, or null."""
        character = getattr(request.user, 'character', None)
        if not character:
            return Response({"detail": "User has no character."}, status=status.HTTP_400_BAD_REQUEST)
        location = (
            _locations_queryset().get(pk=character.current_location_id)
            if character.current_location_id else None
        )
        data = self.get_serializer(location).data if location else None
        return Response({"location": data})

    @action(detail=True, methods=['post'])
    def travel(self, request, pk=None):
        """Move the character here if it meets the region and location level."""
        location = self.get_object()
        if not getattr(request.user, 'character', None):
            return Response({"detail": "User has no character."}, status=status.HTTP_400_BAD_REQUEST)

        with transaction.atomic():
            character = Character.objects.select_for_update().get(pk=request.user.character.pk)
            required_level = max(location.required_level, location.region.required_level)
            if character.level < required_level:
                return Response(
                    {"detail": f"Required level is {required_level}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            if BattleService.get_active_combat_for_character(character):
                return Response(
                    {"detail": "Cannot travel during an active battle."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            character.current_location = location
            character.save(update_fields=['current_location'])

        return Response({"location": self.get_serializer(location).data})
