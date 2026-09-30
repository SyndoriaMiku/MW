from django.db import IntegrityError, transaction


class NovaError(ValueError):
    """A Nova change that is not allowed; the message says why."""


def validate_nova_change(user, amount, kind, balance=None):
    """Why this change is not allowed, or None. `balance` defaults to the user's current Nova."""
    from .models import NovaTransaction

    if isinstance(amount, bool) or not isinstance(amount, int) or amount == 0:
        return 'Amount must be a non-zero whole number.'
    if kind == NovaTransaction.Kind.DONATION and amount < 0:
        return 'A donation must add Nova.'
    if kind == NovaTransaction.Kind.PURCHASE and amount > 0:
        return 'A purchase must spend Nova.'
    if (user.nova if balance is None else balance) + amount < 0:
        return 'Not enough Nova.'
    return None


@transaction.atomic
def record_nova_transaction(entry):
    """
    Apply an unsaved NovaTransaction: lock the user, re-check the change,
    update GameUser.nova and save the entry with the new balance.
    """
    from .models import GameUser, NovaTransaction

    locked = GameUser.objects.select_for_update().get(pk=entry.user_id)
    error = validate_nova_change(locked, entry.amount, entry.kind, balance=locked.nova)
    if error:
        raise NovaError(error)
    entry.reference = (entry.reference or '').strip() or None
    if entry.reference and NovaTransaction.objects.filter(reference=entry.reference).exists():
        raise NovaError('This reference was already credited.')

    locked.nova += entry.amount
    locked.save(update_fields=['nova'])
    entry.balance_after = locked.nova
    try:
        with transaction.atomic():
            entry.save()
    except IntegrityError:
        # A concurrent request credited the same reference.
        raise NovaError('This reference was already credited.')
    # Keep the caller's user instance in step with the database.
    if entry.user is not locked:
        entry.user.nova = locked.nova
    return entry


def change_nova(user, amount, kind, *, reference=None, description='', note='', created_by=None):
    """
    Add (positive) or take (negative) Nova and record it. `reference` is a
    donation/payment id that may be credited once; `description` is shown to
    the player and `note` stays internal. Raises NovaError.
    """
    from .models import NovaTransaction

    return record_nova_transaction(NovaTransaction(
        user=user, kind=kind, amount=amount, reference=reference,
        description=description, note=note, created_by=created_by,
    ))
