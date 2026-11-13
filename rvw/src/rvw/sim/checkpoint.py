"""Live snapshot envelope for adapters with a native save/restore interface.

This module does not turn a reset replay descriptor into a live snapshot.
An adapter must stop at a quiescent boundary and serialize its native model.
"""
from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
from typing import Protocol

SCHEMA = 'rvw.native-checkpoint/1'
IDENTITIES = {'rtl', 'native_build', 'harness', 'stimulus'}
STATE = {'scheduler', 'clock', 'memory', 'pending', 'rng', 'devices',
         'interrupts', 'monitors', 'rvfi', 'stimulus', 'counters'}


class SnapshotPort(Protocol):
    """Adapter-owned port. Methods run while simulation advancement is stopped.

    validate_restore must reject unsupported state without changing the model.
    restore must install native and harness state before resuming execution.
    A restore exception poisons the instance; callers must discard it.
    """
    def quiescent(self) -> bool: ...
    def external_effects(self) -> list[str]: ...
    def save(self) -> tuple[bytes, dict]: ...
    def validate_restore(self, native: bytes, state: dict) -> None: ...
    def restore(self, native: bytes, state: dict) -> None: ...


def _bytes(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(',', ':'),
                      allow_nan=False).encode()


def _identity(identity):
    if not isinstance(identity, dict) or set(identity) != IDENTITIES:
        raise ValueError('checkpoint needs RTL, native build, harness and stimulus identities')
    for value in identity.values():
        if not isinstance(value, str) or len(value) != 64 or any(c not in '0123456789abcdef' for c in value):
            raise ValueError('checkpoint identities must be SHA-256 digests')


def _state(state):
    if not isinstance(state, dict) or set(state) != STATE:
        raise ValueError('checkpoint needs every harness state component')
    # Empty containers explicitly declare empty inventories. Missing state is not empty state.
    if any(value is None for value in state.values()):
        raise ValueError('checkpoint state components must not be null')
    _bytes(state)


def _boundary(port):
    if not port.quiescent():
        raise ValueError('checkpoint requires a quiescent simulation boundary')
    effects = port.external_effects()
    if not isinstance(effects, list) or not all(isinstance(item, str) for item in effects):
        raise ValueError('adapter must declare its external effects inventory')
    if effects:
        raise ValueError(f'checkpoint cannot restore external effects: {effects}')


def save(port: SnapshotPort, path: Path, *, identity: dict) -> dict:
    """Capture native bytes and all harness state in one new envelope file."""
    _identity(identity)
    _boundary(port)
    native, state = port.save()
    if not isinstance(native, bytes) or not native:
        raise ValueError('native checkpoint is empty or not bytes')
    _state(state)
    payload = dict(schema=SCHEMA, identity=identity, state=state,
                   native=base64.b64encode(native).decode('ascii'))
    raw = _bytes(payload)
    envelope = dict(payload=payload, sha256=hashlib.sha256(raw).hexdigest())
    # Do not replace an existing checkpoint when capture fails or paths are reused.
    with Path(path).open('xb') as stream:
        stream.write(_bytes(envelope) + b'\n')
    return dict(schema=SCHEMA, sha256=envelope['sha256'], native_bytes=len(native))


def load(path: Path, *, identity: dict) -> tuple[bytes, dict, str]:
    """Validate the complete envelope before any restore callback can run."""
    _identity(identity)
    try:
        envelope = json.loads(Path(path).read_bytes())
        if set(envelope) != {'payload', 'sha256'}:
            raise ValueError('invalid checkpoint envelope fields')
        payload = envelope['payload']
        if hashlib.sha256(_bytes(payload)).hexdigest() != envelope['sha256']:
            raise ValueError('checkpoint digest mismatch')
        if set(payload) != {'schema', 'identity', 'state', 'native'} or payload['schema'] != SCHEMA:
            raise ValueError('unsupported checkpoint schema')
        if payload['identity'] != identity:
            raise ValueError('checkpoint identity mismatch')
        _state(payload['state'])
        native = base64.b64decode(payload['native'], validate=True)
        if not native:
            raise ValueError('empty native checkpoint')
        return native, payload['state'], envelope['sha256']
    except (KeyError, TypeError, UnicodeError) as exc:
        raise ValueError(f'invalid checkpoint: {exc}') from exc


def restore(port: SnapshotPort, path: Path, *, identity: dict) -> dict:
    """Restore a fresh stopped instance. Never resume after a callback failure."""
    native, state, digest = load(path, identity=identity)
    _boundary(port)
    port.validate_restore(native, state)
    port.restore(native, state)
    return dict(schema=SCHEMA, sha256=digest, status='restored')
