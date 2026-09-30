from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone

from .models import BattleActionReceipt, CombatInstance, Combatant
from .serializers import (
    CombatInstanceSerializer, PlayerActionSerializer
)
from .services import BattleService


def _lock_battle_for_participant(user, combat_id):
    """
    Lock the battle row and find the caller's combatant.
    Returns (combat, combatant, None) or (None, None, error_response).
    """
    # (C-1 fix) Lock combat row — prevents 2 concurrent requests from both executing
    try:
        combat = CombatInstance.objects.select_for_update().get(id=combat_id)
    except CombatInstance.DoesNotExist:
        return None, None, Response({"detail": "Battle not found."}, status=status.HTTP_404_NOT_FOUND)

    try:
        ct = ContentType.objects.get_for_model(user.character)
        combatant = combat.combatants.get(
            is_player=True, content_type=ct, objects_id=str(user.character.id)
        )
    except Combatant.DoesNotExist:
        return None, None, Response({"detail": "You are not in this battle."}, status=status.HTTP_403_FORBIDDEN)
    return combat, combatant, None


def _finish_battle_request(combat, payload, *, state_changed=True):
    """Bump the battle version for a state change and attach the new snapshot."""
    if state_changed:
        # end_turn saves whole combat rows, so bump with an UPDATE afterwards.
        CombatInstance.objects.filter(pk=combat.pk).update(version=F('version') + 1)
    combat.refresh_from_db()
    payload["combat"] = CombatInstanceSerializer(combat).data
    return payload

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_active_battle(request):
    """Return the caller's current battle for scene recovery/reconnect."""
    character = getattr(request.user, 'character', None)
    if character is None:
        return Response({"detail": "You don't have a character."}, status=status.HTTP_400_BAD_REQUEST)

    combat = BattleService.get_active_combat_for_character(character)
    if combat is None:
        return Response(status=status.HTTP_204_NO_CONTENT)
    return Response(CombatInstanceSerializer(combat).data)


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

    action_type = serializer.validated_data['action_type']
    target_id = serializer.validated_data.get('target_id')
    target_position = serializer.validated_data.get('target_position')
    client_action_id = serializer.validated_data.get('client_action_id')
    expected_version = serializer.validated_data.get('expected_version')
    kwargs = {}
    if action_type == 'SKILL':
        kwargs['character_skill_id'] = serializer.validated_data['character_skill_id']
    elif action_type == 'ITEM':
        kwargs['inventory_item_id'] = serializer.validated_data['inventory_item_id']

    with transaction.atomic():
        combat, player_combatant, error = _lock_battle_for_participant(user, combat_id)
        if error:
            return error

        # (CRIT-08) A retry of an executed action replays its stored result.
        # This runs before the state checks: the original action may have
        # ended the battle or passed the turn.
        if client_action_id is not None:
            receipt = BattleActionReceipt.objects.filter(
                combat_instance=combat, client_action_id=client_action_id
            ).first()
            if receipt is not None:
                if receipt.character_id != user.character.pk:
                    return Response(
                        {"detail": "This client_action_id was already used by another participant."},
                        status=status.HTTP_409_CONFLICT,
                    )
                return Response({**receipt.response_data, "replayed": True})

        # Re-check state under lock
        if combat.status != 'in_progress':
            return Response({"detail": "This battle has already ended."}, status=status.HTTP_400_BAD_REQUEST)
        if expected_version is not None and expected_version != combat.version:
            return Response(
                {
                    "detail": "The battle has changed since this action was built. Reload and retry.",
                    "combat": CombatInstanceSerializer(combat).data,
                },
                status=status.HTTP_409_CONFLICT,
            )
        if combat.turn_phase != 'player_phase':
            return Response({"detail": "It's not the player phase."}, status=status.HTTP_400_BAD_REQUEST)
        if player_combatant.position != combat.current_player_position:
            return Response({"detail": "It's not your turn."}, status=status.HTTP_400_BAD_REQUEST)

        if player_combatant.current_hp <= 0:
            payload = {
                "detail": "Your character is dead. Turn skipped.",
                "events": BattleService.end_turn(combat),
            }
            state_changed = True
        else:
            target = None
            if target_id is not None or target_position is not None:
                try:
                    target_lookup = {'id': target_id} if target_id is not None else {'position': target_position}
                    target = combat.combatants.get(**target_lookup)
                except Combatant.DoesNotExist:
                    return Response({"detail": "Invalid target."}, status=status.HTTP_400_BAD_REQUEST)

            log = BattleService.execute_action(player_combatant, action_type, target, **kwargs)
            events = [log]

            # Only advance turn if the action was actually executed (not blocked by cooldown/MP)
            state_changed = log.get("success", True)
            if state_changed:
                combat.refresh_from_db()
                if combat.status == 'in_progress':
                    events.extend(BattleService.end_turn(combat))
            payload = {"action_log": log, "events": events}

        _finish_battle_request(combat, payload, state_changed=state_changed)

        if client_action_id is not None:
            BattleActionReceipt.objects.create(
                combat_instance=combat,
                character=user.character,
                client_action_id=client_action_id,
                response_data=payload,
            )

    return Response({**payload, "replayed": False})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def forfeit_battle(request, combat_id):
    """Leave the battle. A solo player (or the last one standing) loses it."""
    if not request.user.character:
        return Response({"detail": "You don't have a character."}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        combat, combatant, error = _lock_battle_for_participant(request.user, combat_id)
        if error:
            return error
        if combat.status != 'in_progress':
            return Response({"detail": "This battle has already ended."}, status=status.HTTP_400_BAD_REQUEST)
        # A dead player may still leave (giving up the rewards); a player who left may not twice.
        if combatant.has_left:
            return Response({"detail": "You already left this battle."}, status=status.HTTP_400_BAD_REQUEST)

        payload = {"events": BattleService.forfeit(combat, combatant)}
        _finish_battle_request(combat, payload)
    return Response(payload)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def skip_idle_turn(request, combat_id):
    """Let a party member pass the turn of a player idle past the turn timeout."""
    if not request.user.character:
        return Response({"detail": "You don't have a character."}, status=status.HTTP_400_BAD_REQUEST)

    with transaction.atomic():
        combat, combatant, error = _lock_battle_for_participant(request.user, combat_id)
        if error:
            return error
        if combat.status != 'in_progress':
            return Response({"detail": "This battle has already ended."}, status=status.HTTP_400_BAD_REQUEST)
        if combat.turn_phase != 'player_phase':
            return Response({"detail": "It's not the player phase."}, status=status.HTTP_400_BAD_REQUEST)

        idle = combat.combatants.filter(
            is_player=True, position=combat.current_player_position
        ).first()
        if idle is None:
            return Response({"detail": "No player holds the current turn."}, status=status.HTTP_400_BAD_REQUEST)
        if idle.pk == combatant.pk:
            return Response({"detail": "It's your turn; act instead."}, status=status.HTTP_400_BAD_REQUEST)

        turn_started_at = combat.turn_started_at or combat.updated_at
        idle_seconds = (timezone.now() - turn_started_at).total_seconds()
        remaining = settings.BATTLE_TURN_TIMEOUT_SECONDS - idle_seconds
        if remaining > 0:
            return Response(
                {
                    "detail": "The current player's turn has not timed out yet.",
                    "seconds_remaining": int(remaining) + 1,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        payload = {"events": BattleService.skip_turn(combat, idle)}
        _finish_battle_request(combat, payload)
    return Response(payload)
