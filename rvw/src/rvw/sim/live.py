"""Live checkpoint control for project-owned native snapshot ports."""
from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

from . import checkpoint


def _port(manifest):
    path = Path(manifest).resolve(strict=True)
    data = json.loads(path.read_text())
    if data.get('schema') != 'rvw.snapshot-adapter/1':
        raise ValueError('unsupported snapshot adapter manifest')
    module = (path.parent / data['module']).resolve(strict=True)
    identities = {}
    for name in checkpoint.IDENTITIES:
        files = data['identity_files'][name]
        if not isinstance(files, list) or not files:
            raise ValueError('each identity needs input files')
        h = hashlib.sha256()
        for file in files:
            raw = (path.parent / file).read_bytes()
            h.update(len(raw).to_bytes(8, 'big')); h.update(raw)
        identities[name] = h.hexdigest()
    # Include the port source and manifest in the harness identity.
    identities['harness'] = hashlib.sha256(
        bytes.fromhex(identities['harness']) + module.read_bytes() + path.read_bytes()).hexdigest()
    spec = importlib.util.spec_from_file_location('_rvw_snapshot_adapter', module)
    loaded = importlib.util.module_from_spec(spec)
    exec(compile(module.read_bytes(), str(module), 'exec'), loaded.__dict__)
    return loaded.create(data.get('options', {})), identities


def capture(manifest, out, *, cycle=None, instruction=None):
    if (cycle is None) == (instruction is None):
        raise ValueError('select exactly one cycle or instruction boundary')
    target = cycle if cycle is not None else instruction
    if type(target) is not int or target < 1:
        raise ValueError('checkpoint boundary must be positive')
    port, identity = _port(manifest)
    try:
        unit = 'cycles' if cycle is not None else 'instructions'
        port.advance(unit, target)
        if port.position(unit) != target:
            raise ValueError('adapter did not stop at the requested boundary')
        result = checkpoint.save(port, Path(out), identity=identity)
        return dict(result, boundary={unit: target}, status='saved')
    finally:
        port.close()


def resume(manifest, snapshot, out):
    if Path(out).exists():
        raise ValueError('resume needs a new output directory')
    port, identity = _port(manifest)
    try:
        result = checkpoint.restore(port, Path(snapshot), identity=identity)
        # finish writes a fresh C1 run and C2 trace through the adapter.
        # Restored is not an equivalence verdict. Use suffix-check separately.
        return dict(result, result=port.finish(Path(out)))
    finally:
        port.close()


def suffix_check(original, resumed, *, position):
    """Compare exact C2 bytes after a saved writer byte position, including end."""
    if type(position) is not int or position < 0:
        raise ValueError('position must be a nonnegative byte offset')
    original = Path(original).read_bytes()
    resumed = Path(resumed).read_bytes()
    if position >= len(original) or (position and original[position - 1:position] != b'\n'):
        raise ValueError('position must start a nonempty C2 line suffix')
    for raw in (original, resumed):
        rows = [json.loads(line) for line in raw.splitlines()]
        if not rows or rows[0].get('schema') not in ('rvw.rvfi/1', 'rvw.rvfi/2') or rows[-1].get('event') != 'end':
            raise ValueError('complete C2 header and end event required')
    if original[:position] != resumed[:position]:
        raise ValueError('restored C2 prefix mismatch')
    if original[position:] != resumed[position:]:
        raise ValueError('restored C2 suffix mismatch')
    return dict(status='equivalent', suffix_bytes=len(original) - position,
                suffix_sha256=hashlib.sha256(original[position:]).hexdigest())


def command(a):
    try:
        if a.snapshot_action == 'reverse-step':
            from .reverse import reverse_step
            result = reverse_step(a.manifest, a.snapshot, a.out, current=a.current,
                                  target=a.target, max_seconds=a.max_seconds)
        elif a.snapshot_action == 'checkpoint':
            result = capture(a.manifest, a.out, cycle=a.cycle, instruction=a.instruction)
        elif a.snapshot_action == 'resume':
            result = resume(a.manifest, a.snapshot, a.out)
        else:
            result = suffix_check(a.original, a.resumed, position=a.position)
        print(json.dumps(result))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps(dict(status='error', message=str(exc))))
        return 2


def register(sub):
    sim = sub.add_parser('sim', help='native simulation checkpoint control')
    commands = sim.add_subparsers(dest='snapshot_action', required=True)
    p = commands.add_parser('timing-handoff', help='check an external gate-netlist/SDF capability declaration')
    p.add_argument('manifest', type=Path)
    p.add_argument('--capabilities', type=Path, required=True)
    from .timing import command as timing_command
    p.set_defaults(func=timing_command)
    p = commands.add_parser('profile', help='report recorded C1 native build and run costs')
    p.add_argument('--result', action='append', type=Path, default=[])
    p.add_argument('--build-profile', choices=('default', 'threads-2', 'threads-4', 'split-10000'), default='default')
    p.add_argument('--out', type=Path)
    from .profile import command as profile_command
    p.set_defaults(func=profile_command)
    p = commands.add_parser('checkpoint', help='capture a project native snapshot port')
    p.add_argument('manifest', type=Path)
    group = p.add_mutually_exclusive_group(required=True)
    group.add_argument('--cycle', type=int)
    group.add_argument('--instruction', type=int)
    p.add_argument('--out', type=Path, required=True)
    p.set_defaults(func=command)
    p = commands.add_parser('resume', help='restore a native snapshot in a fresh adapter')
    p.add_argument('manifest', type=Path)
    p.add_argument('snapshot', type=Path)
    p.add_argument('--out', type=Path, required=True)
    p.set_defaults(func=command)
    p = commands.add_parser('reverse-step', help='restore a checkpoint and execute forward to an earlier instruction')
    p.add_argument('manifest', type=Path)
    p.add_argument('--snapshot', action='append', type=Path, required=True)
    p.add_argument('--current', type=int, required=True)
    p.add_argument('--target', type=int, required=True)
    p.add_argument('--max-seconds', type=float, default=30)
    p.add_argument('--out', type=Path, required=True)
    p.set_defaults(func=command)
    p = commands.add_parser('suffix-check', help='compare complete resumed C2 suffix bytes')
    p.add_argument('original', type=Path)
    p.add_argument('resumed', type=Path)
    p.add_argument('--position', type=int, required=True)
    p.set_defaults(func=command)
