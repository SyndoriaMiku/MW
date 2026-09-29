"""
Parse loose request values (JSON body fields, query strings) that views read
without a serializer. Bad input raises a DRF ValidationError, which DRF turns
into a 400, instead of reaching int()/float() or an ORM lookup and becoming a 500.
"""
import math

from rest_framework.exceptions import ValidationError


def parse_int(value, field, *, min_value=None):
    """Return `value` as an int, or None when it is missing/blank."""
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        raise ValidationError({field: 'A valid integer is required.'})
    if isinstance(value, int):
        result = value
    elif isinstance(value, str) and value.strip().lstrip('-').isdigit():
        result = int(value)
    else:
        raise ValidationError({field: 'A valid integer is required.'})
    if min_value is not None and result < min_value:
        raise ValidationError({field: f'Ensure this value is greater than or equal to {min_value}.'})
    return result


def parse_float(value, field):
    """Return `value` as a finite float, or None when it is missing/blank."""
    if value is None or value == '':
        return None
    if isinstance(value, bool):
        raise ValidationError({field: 'A valid number is required.'})
    try:
        result = float(value)
    except (TypeError, ValueError):
        raise ValidationError({field: 'A valid number is required.'})
    if not math.isfinite(result):
        raise ValidationError({field: 'A valid number is required.'})
    return result
