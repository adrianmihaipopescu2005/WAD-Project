"""A small in-memory rate limiter for the public pages (decided 2026-10-26, no extra dependency).

Sliding window per (rule, client IP). The state lives in this process only, so it resets on
restart and isn't shared between several worker processes. That's enough for this project.
"""

import threading
import time
from collections import defaultdict, deque
from functools import wraps

from flask import abort, current_app, request

_hits = defaultdict(deque)
_lock = threading.Lock()


def _allowed(key, limit, per_seconds):
    now = time.monotonic()
    with _lock:
        window = _hits[key]
        while window and now - window[0] >= per_seconds:
            window.popleft()
        if len(window) >= limit:
            return False
        window.append(now)
        return True


def reset():
    with _lock:
        _hits.clear()


def rate_limit(name, limit, per_seconds=60, methods=("GET", "POST")):
    """Allow `limit` requests per `per_seconds` for each client IP, otherwise answer 429."""

    def decorator(view):
        @wraps(view)
        def wrapped(*args, **kwargs):
            if (
                current_app.config.get("RATELIMIT_ENABLED", True)
                and request.method in methods
                and not _allowed((name, request.remote_addr), limit, per_seconds)
            ):
                abort(429, description="Too many requests. Wait a minute and try again.")
            return view(*args, **kwargs)

        return wrapped

    return decorator
