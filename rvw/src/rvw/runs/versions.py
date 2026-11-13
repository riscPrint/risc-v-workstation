"""Resolve captured, project-owned adapters for historical core revisions."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

API_VERSION = 1
MANIFEST = '.rvw-adapters.json'


def resolve(source: Path, revision: str | None):
    """Return None for legacy projects, or an identity and captured command.

    A project can select exact revision entries or read a version marker from
    the captured core tree. No Git lookup or mutable checkout is needed.
    """
    source = Path(source).resolve()
    path = source / MANIFEST
    if not path.exists():
        return None
    raw = path.read_bytes()
    doc = json.loads(raw)
    if doc.get('schema') != 'rvw.adapter-versions/1':
        raise ValueError('unsupported adapter version manifest')
    revisions = doc.get('revisions', {})
    version = revisions.get(revision)
    if version is None and doc.get('marker'):
        marker = _inside(source, doc['marker'])
        version = marker.read_text().strip()
    if not version or version not in doc['adapters']:
        raise ValueError(f'unsupported revision: no simulation adapter for {revision}')
    entry = doc['adapters'][version]
    if entry.get('api') != API_VERSION:
        raise ValueError(f'unsupported adapter API: {entry.get("api")}')
    command = entry['command']
    if not isinstance(command, list) or not command or not all(isinstance(x, str) and x for x in command):
        raise ValueError('adapter command must be a nonempty argv list')
    # Commands are captured scripts/executables, not shell strings. Interpreter
    # selection remains the launcher's responsibility; scripts use a shebang.
    executable = _inside(source, command[0])
    if not executable.is_file():
        raise ValueError('selected adapter executable is missing')
    identity = dict(schema='rvw.adapter-selection/1', api=API_VERSION, version=version,
                    revision=revision, manifest_sha256=hashlib.sha256(raw).hexdigest(),
                    executable_sha256=hashlib.sha256(executable.read_bytes()).hexdigest())
    return [str(executable), *command[1:]], identity


def _inside(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root) or Path(relative).is_absolute():
        raise ValueError('adapter paths must stay in the captured source tree')
    return path
