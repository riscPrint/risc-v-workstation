"""One wall budget for native flow preparation and execution."""
from contextlib import contextmanager
from contextvars import ContextVar
import time

_active = ContextVar('security_budget', default=None)


class BudgetExpired(ValueError):
    pass


@contextmanager
def limit(seconds):
    started = time.monotonic()
    token = _active.set((started, seconds))
    try:
        yield
    finally:
        _active.reset(token)


def remaining(default):
    active = _active.get()
    if active is None:
        return default
    left = active[1] - (time.monotonic()-active[0])
    if left <= 0:
        raise BudgetExpired('security wall budget expired')
    return min(left, default)
