"""
Failed-login limits. Only wrong credentials count: an account is locked after
LOGIN_FAILURE_LIMIT_PER_USER failures and an IP after LOGIN_FAILURE_LIMIT_PER_IP,
each until LOGIN_FAILURE_WINDOW_SECONDS after its first counted failure.

Counters live in Django's cache. The default local-memory cache is per process,
so production with several workers needs a shared cache (e.g. Redis) for the
limits to hold across workers.
"""
import math
import time

from django.conf import settings
from django.core.cache import cache


def _key(kind, value):
    return f'login-failures:{kind}:{value}'


def _keys(username, ip):
    # Usernames are matched case-insensitively so "Victim" and "victim" share a counter.
    return {
        _key('user', (username or '').strip().lower()): settings.LOGIN_FAILURE_LIMIT_PER_USER,
        _key('ip', ip): settings.LOGIN_FAILURE_LIMIT_PER_IP,
    }


def _current(key, now):
    """(count, first_failure_at) for a window that has not ended yet, else None."""
    entry = cache.get(key)
    if entry is None or entry['first_at'] + settings.LOGIN_FAILURE_WINDOW_SECONDS <= now:
        return None
    return entry


def seconds_locked(username, ip):
    """Seconds until this login may be tried again, or 0 when it is allowed now."""
    now = time.time()
    wait = 0
    for key, limit in _keys(username, ip).items():
        entry = _current(key, now)
        if entry and entry['count'] >= limit:
            ends = entry['first_at'] + settings.LOGIN_FAILURE_WINDOW_SECONDS
            wait = max(wait, math.ceil(ends - now))
    return wait


def record_failure(username, ip):
    now = time.time()
    window = settings.LOGIN_FAILURE_WINDOW_SECONDS
    for key in _keys(username, ip):
        entry = _current(key, now) or {'count': 0, 'first_at': now}
        entry['count'] += 1
        cache.set(key, entry, timeout=max(1, math.ceil(entry['first_at'] + window - now)))


def record_success(username):
    """A correct login clears the account's counter; the IP's stays."""
    cache.delete(_key('user', (username or '').strip().lower()))
