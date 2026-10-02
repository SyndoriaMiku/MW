"""The safe actions Studio offers on a player account; each reuses the game's own rules."""
import secrets
import string

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from apps.battles.models import CombatInstance, Combatant
from apps.battles.services import BattleService
from apps.users.sessions import end_all_sessions

# No look-alike characters (0/O, 1/l/I), so a password read aloud or retyped survives.
PASSWORD_ALPHABET = ''.join(ch for ch in string.ascii_letters + string.digits if ch not in '0O1lI')


def temporary_password(length=12):
    return ''.join(secrets.choice(PASSWORD_ALPHABET) for _ in range(length))


def set_locked(user, locked):
    """Lock (and log out everywhere) or unlock an account."""
    user.is_active = not locked
    user.save(update_fields=['is_active'])
    if locked:
        end_all_sessions(user)


def reset_password(user):
    """Give the account a new random password; set_password ends every session."""
    password = temporary_password()
    user.set_password(password)
    user.save(update_fields=['password', 'session_version'])
    return password


def end_stuck_battle(character):
    """
    Take the character out of its running battle as a forfeit would: no
    rewards, and a battle with nobody left is lost. Returns the battle, or
    None when there is none.
    """
    combat = BattleService.get_active_combat_for_character(character)
    if combat is None:
        return None
    with transaction.atomic():
        combat = CombatInstance.objects.select_for_update().get(pk=combat.pk)
        combatant = Combatant.objects.get(
            combat_instance=combat, is_player=True, has_left=False,
            content_type=ContentType.objects.get_for_model(character), objects_id=str(character.pk),
        )
        BattleService.forfeit(combat, combatant)
        CombatInstance.objects.filter(pk=combat.pk).update(version=F('version') + 1)
    combat.refresh_from_db()
    return combat


def refill_stamina(character):
    character.current_stamina = character.max_stamina
    character.last_stamina_update = timezone.now()
    character.save(update_fields=['current_stamina', 'last_stamina_update'])
