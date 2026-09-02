from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.db import transaction
from django.contrib.contenttypes.models import ContentType

from .models import CombatInstance, Combatant
from .serializers import (
    CombatInstanceSerializer, PlayerActionSerializer
)
from .services import BattleService


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_battle_state(request, combat_id):
    """
    Get the current state of a battle.
    """
    user = request.user
    if not user.character:
        return Response({"detail": "You don't have a character."}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        combat = CombatInstance.objects.get(id=combat_id)
    except CombatInstance.DoesNotExist:
        return Response({"detail": "Battle not found."}, status=status.HTTP_404_NOT_FOUND)
    
    # Check if the user's character is a combatant
    ct = ContentType.objects.get_for_model(user.character)
    is_participant = combat.combatants.filter(
        is_player=True, content_type=ct, objects_id=str(user.character.id)
    ).exists()
    
    if not is_participant:
        return Response({"detail": "You are not a participant in this battle."}, status=status.HTTP_403_FORBIDDEN)
    
    return Response(CombatInstanceSerializer(combat).data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def player_action(request, combat_id):
    """
    Execute a player action (ATTACK or SKILL) during combat.
    """
    serializer = PlayerActionSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    user = request.user
    if not user.character:
        return Response({"detail": "You don't have a character."}, status=status.HTTP_400_BAD_REQUEST)

    # Pre-validate outside transaction for fast-fail
    try:
        pre_check = CombatInstance.objects.only('id', 'status', 'turn_phase').get(id=combat_id)
    except CombatInstance.DoesNotExist:
        return Response({"detail": "Battle not found."}, status=status.HTTP_404_NOT_FOUND)

    if pre_check.status != 'in_progress':
        return Response({"detail": "This battle has already ended."}, status=status.HTTP_400_BAD_REQUEST)
    if pre_check.turn_phase != 'player_phase':
        return Response({"detail": "It's not the player phase."}, status=status.HTTP_400_BAD_REQUEST)

    action_type = serializer.validated_data['action_type']
    target_position = serializer.validated_data['target_position']
    kwargs = {}
    if action_type == 'SKILL':
        skill_id = serializer.validated_data.get('skill_id')
        if not skill_id:
            return Response({"detail": "skill_id is required for SKILL action."}, status=status.HTTP_400_BAD_REQUEST)
        kwargs['skill_id'] = skill_id

    log = None
    with transaction.atomic():
        # (C-1 fix) Lock combat row — prevents 2 concurrent requests from both executing
        try:
            combat = CombatInstance.objects.select_for_update().get(id=combat_id)
        except CombatInstance.DoesNotExist:
            return Response({"detail": "Battle not found."}, status=status.HTTP_404_NOT_FOUND)

        # Re-check state under lock
        if combat.status != 'in_progress':
            return Response({"detail": "This battle has already ended."}, status=status.HTTP_400_BAD_REQUEST)
        if combat.turn_phase != 'player_phase':
            return Response({"detail": "It's not the player phase."}, status=status.HTTP_400_BAD_REQUEST)

        try:
            ct = ContentType.objects.get_for_model(user.character)
            player_combatant = combat.combatants.get(
                is_player=True, content_type=ct, objects_id=str(user.character.id)
            )
        except Combatant.DoesNotExist:
            return Response({"detail": "You are not in this battle."}, status=status.HTTP_403_FORBIDDEN)

        if player_combatant.position != combat.current_player_position:
            return Response({"detail": "It's not your turn."}, status=status.HTTP_400_BAD_REQUEST)

        if player_combatant.current_hp <= 0:
            BattleService.end_turn(combat)
            combat.refresh_from_db()
            return Response({
                "detail": "Your character is dead. Turn skipped.",
                "combat": CombatInstanceSerializer(combat).data
            })

        try:
            target = combat.combatants.get(position=target_position)
        except Combatant.DoesNotExist:
            return Response({"detail": "Invalid target."}, status=status.HTTP_400_BAD_REQUEST)

        log = BattleService.execute_action(player_combatant, action_type, target, **kwargs)

        # Only advance turn if the action was actually executed (not blocked by cooldown/MP)
        if log.get("success", True):
            combat.refresh_from_db()
            if combat.status == 'in_progress':
                BattleService.end_turn(combat)

    combat.refresh_from_db()
    return Response({
        "action_log": log,
        "combat": CombatInstanceSerializer(combat).data
    })
