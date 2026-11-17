from collections import deque
from contextlib import contextmanager
from dataclasses import dataclass, field
from math import ceil
from threading import Lock
from time import monotonic

from fastapi import HTTPException


MAX_FAILURES = 5
WINDOW_SECONDS = 60


@dataclass
class LoginAttempts:
    failures: deque[float] = field(default_factory=deque)
    pending: int = 0

    def discard_expired(self, now: float):
        while self.failures and self.failures[0] <= now - WINDOW_SECONDS:
            self.failures.popleft()


class LoginLimiter:
    def __init__(self):
        self.lock = Lock()
        self.attempts: dict[tuple[str, str], LoginAttempts] = {}
        self.next_cleanup = 0.0

    @contextmanager
    def attempt(self, host: str, username: str):
        key = (host, username)
        with self.lock:
            now = monotonic()
            if now >= self.next_cleanup:
                for old_key, old in list(self.attempts.items()):
                    old.discard_expired(now)
                    if not old.failures and not old.pending:
                        del self.attempts[old_key]
                self.next_cleanup = now + WINDOW_SECONDS

            attempts = self.attempts.setdefault(key, LoginAttempts())
            attempts.discard_expired(now)
            if len(attempts.failures) + attempts.pending >= MAX_FAILURES:
                retry_after = 1
                if len(attempts.failures) >= MAX_FAILURES:
                    retry_after = max(1, ceil(attempts.failures[0] + WINDOW_SECONDS - now))
                raise HTTPException(
                    status_code=429,
                    detail={"error": "Слишком много попыток входа", "field": "authorization"},
                    headers={"Retry-After": str(retry_after)},
                )
            attempts.pending += 1

        failed = False
        try:
            yield
        except HTTPException as error:
            failed = error.status_code == 401
            raise
        finally:
            with self.lock:
                attempts.pending -= 1
                if failed:
                    attempts.failures.append(monotonic())
                if not attempts.pending and not attempts.failures:
                    del self.attempts[key]
