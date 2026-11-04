"""Run pinned official litmus tests on herd, then check project DUT outcomes."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

from rvw.common.proc import run_group

PINS = Path(__file__).with_name('litmus-pins.json')


def tree_digest(root):
    h = hashlib.sha256()
    for path in sorted(root.rglob('*')):
        if path.is_file():
            h.update(str(path.relative_to(root)).encode() + b'\0' + path.read_bytes() + b'\0')
    return h.hexdigest()


def canonical(state):
    if not state or any(not re.fullmatch(r'\d+:x\d+', k) or type(v) is not int for k, v in state.items()):
        raise ValueError('expected integer final register values keyed by hart:xN')
    return tuple(sorted(state.items()))


def parse_states(text):
    lines = text.splitlines()
    headers = [i for i, line in enumerate(lines) if re.fullmatch(r'States \d+', line)]
    if len(headers) != 1:
        raise ValueError('missing or ambiguous herd state list')
    index = headers[0]
    count = int(lines[index].split()[1])
    if count <= 0:
        raise ValueError('empty allowed set')
    states = set()
    for line in lines[index+1:index+1+count]:
        fields = line.split(';')
        state = {}
        for field in fields:
            if not field.strip():
                continue
            match = re.fullmatch(r'\s*(\d+:x\d+)=(-?(?:0x[0-9a-fA-F]+|\d+))\s*', field)
            if not match or match[1] in state:
                raise ValueError('unsupported or duplicate herd outcome field')
            state[match[1]] = int(match[2], 16 if '0x' in match[2] else 10)
        states.add(canonical(state))
    if len(states) != count or not any(line.startswith('Observation ') for line in lines):
        raise ValueError('incomplete herd output')
    if len({tuple(k for k, _ in state) for state in states}) != 1:
        raise ValueError('unequal outcome projections')
    return states


def compare(allowed, sample):
    result = {'status': 'inconclusive', 'forbidden': [], 'permitted_not_observed': []}
    rows = sample.get('observations', [])
    if type(sample.get('harts')) is not int or sample['harts'] < 2 or sample.get('complete') is not True or not rows:
        return result | {'reason': 'complete multi-hart samples required'}
    observed = set()
    keys = set(dict(next(iter(allowed))))
    for row in rows:
        if type(row.get('count')) is not int or row['count'] <= 0:
            return result | {'reason': 'positive outcome counts required'}
        try:
            state = canonical(row['state'])
        except (KeyError, TypeError, ValueError):
            return result | {'reason': 'invalid observed outcome'}
        if set(dict(state)) != keys:
            return result | {'reason': 'observed register projection differs from model'}
        observed.add(state)
    return result | {'status': 'mismatch' if observed - allowed else 'consistent',
                     'forbidden': [dict(s) for s in sorted(observed - allowed)],
                     'permitted_not_observed': [dict(s) for s in sorted(allowed - observed)],
                     'exhaustive_proof': False}


def checked(command, timeout=120):
    result = run_group(command, timeout=timeout, capture=True)
    if result.returncode:
        raise ValueError(f'command failed ({result.returncode}): {command}: {result.stderr}')
    return result.stdout


def validate_pins(tests, source, pins):
    for root, key in [(tests, 'tests'), (source, 'herd')]:
        if checked(['git', '-C', str(root), 'rev-parse', 'HEAD']).strip() != pins[key]['rev']:
            raise ValueError(f'{key} revision differs from pin')
    libdir = source / 'herd/libdir'
    if tree_digest(libdir) != pins['herd']['libdir_sha256']:
        raise ValueError('herd model library bytes differ from pin')
    for case, digest in pins['cases'].items():
        if hashlib.sha256((tests / case).read_bytes()).hexdigest() != digest:
            raise ValueError(f'litmus bytes differ from pin: {case}')
    return libdir


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--tests', type=Path, required=True)
    p.add_argument('--herd-source', type=Path, required=True)
    p.add_argument('--herd', default='herd7')
    p.add_argument('--out', type=Path, required=True)
    p.add_argument('--dut-adapter', type=Path, help='project executable: TEST.litmus -> outcome JSON on stdout')
    args = p.parse_args()
    pins = json.loads(PINS.read_text())
    args.out.mkdir(parents=True, exist_ok=True)
    try:
        libdir = validate_pins(args.tests, args.herd_source, pins)
        version = checked([args.herd, '-version']).strip()
        if not re.match(r'7\.58(?:,|\s|$)', version):
            raise ValueError('herd executable version differs from pin')
        executable = Path(shutil.which(args.herd) or args.herd).resolve()
        report = {'pins': pins, 'herd_version': version,
                  'herd_executable_sha256': hashlib.sha256(executable.read_bytes()).hexdigest(), 'cases': [], 'dut': 'not_run'}
        for case in pins['cases']:
            test = args.tests / case
            output = checked([args.herd, '-I', str(libdir), '-model', str(libdir / 'riscv.cat'), str(test)])
            (args.out / (test.stem + '.herd.log')).write_text(output)
            allowed = parse_states(output)
            row = {'test': case, 'allowed': [dict(s) for s in sorted(allowed)], 'dut': 'not_run'}
            if args.dut_adapter:
                row['dut'] = compare(allowed, json.loads(checked([str(args.dut_adapter.resolve()), str(test.resolve())])))
            report['cases'].append(row)
        states = [r['dut']['status'] for r in report['cases']] if args.dut_adapter else []
        report['dut'] = ('mismatch' if 'mismatch' in states else
                         'inconclusive' if 'inconclusive' in states else 'consistent' if states else 'not_run')
        (args.out / 'outcomes.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
        return 1 if report['dut'] == 'mismatch' else 3 if report['dut'] == 'inconclusive' else 0
    except (ValueError, OSError, json.JSONDecodeError) as error:
        print(json.dumps({'status': 'inconclusive', 'reason': str(error)}))
        return 3


if __name__ == '__main__':
    raise SystemExit(main())
