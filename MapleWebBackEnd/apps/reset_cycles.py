"""
Calendar reset periods shared by boss clears, periodic quests and shop limits.

Periods start at midnight in the server time zone (settings.TIME_ZONE): daily
every day, weekly on Monday, monthly on the 1st.
"""
from datetime import timedelta

from django.utils import timezone

DAILY = 'daily'
WEEKLY = 'weekly'
MONTHLY = 'monthly'


def period_start(cycle, now=None):
    """Return when the current `cycle` period began."""
    local_now = timezone.localtime(now or timezone.now())
    midnight = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    if cycle == DAILY:
        return midnight
    if cycle == WEEKLY:
        return midnight - timedelta(days=midnight.weekday())
    if cycle == MONTHLY:
        return midnight.replace(day=1)
    raise ValueError(f'Unknown reset cycle: {cycle!r}')


def is_current_period(moment, cycle, now=None):
    """True when `moment` falls in the current `cycle` period."""
    return moment >= period_start(cycle, now)
