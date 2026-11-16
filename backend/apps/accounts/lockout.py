"""Per-account brute-force protection, on top of the per-IP login limit.

After LOCK_AFTER failed attempts within the window the account refuses logins
for LOCK_SECONDS, whichever IPs the attempts came from. A successful password
reset or login clears the counter. Counters live in the cache (Redis).
"""

from django.core.cache import cache

LOCK_AFTER = 10
WINDOW_SECONDS = 15 * 60
LOCK_SECONDS = 15 * 60


def _key(email: str) -> str:
    return f"login-fail:{email.strip().lower()}"


def account_locked(email: str) -> bool:
    return (cache.get(_key(email)) or 0) >= LOCK_AFTER


def note_failed_login(email: str) -> None:
    key = _key(email)
    if cache.add(key, 1, WINDOW_SECONDS):
        return
    try:
        n = cache.incr(key)
    except ValueError:  # expired between add and incr
        cache.set(key, 1, WINDOW_SECONDS)
        return
    if n >= LOCK_AFTER:
        cache.touch(key, LOCK_SECONDS)


def clear_failed_logins(email: str) -> None:
    cache.delete(_key(email))
