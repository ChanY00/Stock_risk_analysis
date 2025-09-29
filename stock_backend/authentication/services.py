from __future__ import annotations

from django.conf import settings
from django.core.cache import cache
from typing import Optional


def get_client_ip(request) -> str:
    """Best-effort client IP extraction suitable for rate limiting."""
    xff = request.META.get('HTTP_X_FORWARDED_FOR')
    if xff:
        # XFF may contain multiple, use the first
        return xff.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', '')


def _attempts_key(username: str, ip: str) -> str:
    prefix = getattr(settings, 'CACHE_KEY_PREFIX', '')
    return f"{prefix}auth:attempts:{username}:{ip}"


def _lock_key(username: str, ip: str) -> str:
    prefix = getattr(settings, 'CACHE_KEY_PREFIX', '')
    return f"{prefix}auth:lock:{username}:{ip}"


def is_locked(username: str, ip: str) -> bool:
    return bool(cache.get(_lock_key(username, ip)))


def record_failed_attempt(username: str, ip: str) -> int:
    """Increment failed attempts counter within attempt window; returns current count."""
    key = _attempts_key(username, ip)
    attempts = cache.get(key)
    window = int(getattr(settings, 'AUTH_ATTEMPT_WINDOW_SECONDS', 600))
    if attempts is None:
        cache.set(key, 1, timeout=window)
        return 1
    try:
        # incr preserves original TTL in most backends
        return cache.incr(key)
    except Exception:
        attempts = int(attempts) + 1
        cache.set(key, attempts, timeout=window)
        return attempts


def lock_account(username: str, ip: str) -> None:
    lock_seconds = int(getattr(settings, 'AUTH_LOCKOUT_SECONDS', 300))
    cache.set(_lock_key(username, ip), True, timeout=lock_seconds)


def reset_attempts(username: str, ip: str) -> None:
    cache.delete_many([_attempts_key(username, ip), _lock_key(username, ip)])


