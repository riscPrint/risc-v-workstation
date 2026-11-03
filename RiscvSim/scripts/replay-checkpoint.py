#!/usr/bin/env python3
"""Save a from-reset replay checkpoint and check a later trace suffix.

This is a replay descriptor, not a live DUT snapshot. It makes no ISA claim.
"""
import argparse
import hashlib
import json
from pathlib import Path


IDENTITY = ('core', 'config', 'elf_sha256', 'rtl_sha256', 'seed', 'max_cycles',
            'mem_latency', 'irq_schedule')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def load_run(path, cycle):
    path = Path(path).resolve()
    raw = path.read_bytes()
    result = json.loads(raw)
    if result.get('schema') != 'rvw.run/1' or result.get('inconclusive'):
        raise ValueError('checkpoint requires conclusive C1 evidence')
    if result.get('wall_clock_timeout') or result.get('status') not in ('pass', 'fail', 'timeout'):
        raise ValueError('checkpoint requires a completed simulation')
    for key in ('elf_sha256', 'rtl_sha256'):
        value = result.get(key)
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError('missing identity: ' + key)
    native = result.get('tools', {}).get('native_build', {}).get('sha256')
    if not native:
        raise ValueError('missing native build identity')
    trace_path = Path(result['artifacts']['rvfi_trace'])
    if trace_path.is_absolute() or '..' in trace_path.parts:
        raise ValueError('trace must be inside the run directory')
    trace = (path.parent / trace_path).read_bytes()
    events = [json.loads(line) for line in trace.splitlines()]
    if not events or events[-1].get('event') != 'end':
        raise ValueError('trace has no end event')
    if cycle < 1 or cycle >= result['cycles']:
        raise ValueError('checkpoint cycle must be inside the run')
    suffix = [e for e in events if e.get('cycle', -1) >= cycle]
    if not suffix:
        raise ValueError('trace has no suffix')
    identity = {key: result.get(key) for key in IDENTITY}
    identity['native_sha256'] = native
    identity['source'] = result.get('source')
    identity['model'] = result.get('details', {}).get('model')
    identity['terminal'] = {k: result.get(k) for k in ('status', 'cycles', 'instret', 'fail_code')}
    return dict(result=str(path), result_sha256=digest(raw), trace_sha256=digest(trace),
                identity=identity, suffix=suffix)


def create(result, cycle, out):
    record = load_run(result, cycle)
    body = dict(schema='rvw.replay-checkpoint/1', mode='from-reset', cycle=cycle, **record)
    body['id'] = digest(json.dumps(body, sort_keys=True, separators=(',', ':')).encode())
    Path(out).write_text(json.dumps(body, indent=2) + '\n')
    return body


def verify(checkpoint, result):
    saved = json.loads(Path(checkpoint).read_bytes())
    claimed = saved.pop('id')
    if saved.get('schema') != 'rvw.replay-checkpoint/1' or saved.get('mode') != 'from-reset':
        raise ValueError('unsupported replay checkpoint')
    if digest(json.dumps(saved, sort_keys=True, separators=(',', ':')).encode()) != claimed:
        raise ValueError('checkpoint identity mismatch')
    original = load_run(saved['result'], saved['cycle'])
    if any(original[k] != saved[k] for k in original):
        raise ValueError('original evidence changed')
    replay = load_run(result, saved['cycle'])
    if replay['identity'] != saved['identity']:
        raise ValueError('replay input or model identity mismatch')
    if replay['suffix'] != saved['suffix']:
        raise ValueError('replay suffix mismatch')
    return dict(schema='rvw.replay-equivalence/1', status='equivalent',
                checkpoint=claimed, cycle=saved['cycle'], events=len(replay['suffix']))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    save = commands.add_parser('save')
    save.add_argument('--result', required=True)
    save.add_argument('--cycle', type=int, required=True)
    save.add_argument('--out', required=True)
    check = commands.add_parser('verify')
    check.add_argument('--checkpoint', required=True)
    check.add_argument('--result', required=True)
    args = parser.parse_args()
    try:
        value = (create(args.result, args.cycle, args.out) if args.command == 'save'
                 else verify(args.checkpoint, args.result))
    except (ValueError, KeyError, TypeError, OSError) as error:
        print(json.dumps(dict(status='error', message=str(error))))
        return 2
    print(json.dumps(value))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
