"""Shared race fixture. Import ``race_injector`` in a test module to enable it.

Hook a named callable instead of using sleeps. ``file(..., revert=True)`` changes
an input for that call, then restores its bytes before the caller continues.
"""
from dataclasses import dataclass
from functools import wraps
import os
from pathlib import Path
import tempfile

import pytest


@dataclass
class Injection:
    calls: int = 0
    fired: bool = False


class RaceInjector:
    def __init__(self, monkeypatch):
        self.monkeypatch = monkeypatch

    def at(self, target, attribute, action, *, when='after', restore=None, occurrence=1):
        """Run action before/after the selected call; restore even if that call raises."""
        if when not in ('before', 'after') or occurrence < 1:
            raise ValueError('invalid race boundary')
        original = getattr(target, attribute)
        state = Injection()

        @wraps(original)
        def boundary(*args, **kwargs):
            state.calls += 1
            selected = state.calls == occurrence
            if not selected:
                return original(*args, **kwargs)
            state.fired = True
            try:
                if when == 'before':
                    action()
                result = original(*args, **kwargs)
                if when == 'after':
                    action()
                return result
            finally:
                if restore is not None:
                    restore()

        self.monkeypatch.setattr(target, attribute, boundary)
        return state

    def file(self, target, attribute, path, data, *, when='before', replace=False,
             revert=False, occurrence=1):
        """Edit or atomically replace a file at a call; optionally restore it on return."""
        path = Path(path)
        old, mode = path.read_bytes(), path.stat().st_mode & 0o777

        def write(content):
            if not replace:
                path.write_bytes(content)
                return
            fd, name = tempfile.mkstemp(dir=path.parent)
            try:
                with os.fdopen(fd, 'wb') as stream:
                    stream.write(content)
                os.chmod(name, mode)
                os.replace(name, path)
            finally:
                Path(name).unlink(missing_ok=True)

        return self.at(target, attribute, lambda: write(data), when=when,
                       restore=(lambda: write(old)) if revert else None, occurrence=occurrence)


@pytest.fixture
def race_injector(monkeypatch):
    return RaceInjector(monkeypatch)
