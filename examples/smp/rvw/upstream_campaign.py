#!/usr/bin/env python3
"""Prepare the full applicable pinned scalar subset and check native outcomes."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import runpy
import time

from rvw.common.proc import run_group
from litmus_catalog import PIN, build, catalog, parse_text
from litmus_capture import capture

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]


def prepare(tests, out):
    tests, out = Path(tests).resolve(), Path(out).resolve()
    rows = catalog(tests)
    out.mkdir(parents=True, exist_ok=False)
    jobs = []
    for index, row in enumerate(rows):
        if row['status'] != 'applicable':
            continue
        row['name'] = f'case-{index:05d}'
        folder = out/row['name']
        build(tests/row['test'], folder)
        jobs.append(dict(elf=str(folder/'hart-0.elf'), hart_images=str(folder/'hart-images.json'),
                         out=str(out/(row['name']+'-run')), config=f"smp{row['harts']}", seed=17,
                         max_cycles=200000, wall_timeout=120, rvfi_trace=True))
    report = dict(schema='rvw.upstream-litmus/1', revision=PIN, cases=rows,
                  counts=dict(Counter(r['status'] for r in rows)))
    (out/'catalog.json').write_text(json.dumps(report, indent=2)+'\n')
    (out/'jobs.jsonl').write_text(''.join(json.dumps(j)+'\n' for j in jobs))
    return report['counts']


def summarize(tests, out, herd, herd_source):
    tests, out = Path(tests).resolve(), Path(out).resolve()
    model = runpy.run_path(str(ROOT/'RiscvSim/tests/ordering/litmus.py'))
    pins = json.loads((ROOT/'RiscvSim/tests/ordering/litmus-pins.json').read_text())
    libdir = model['validate_pins'](tests, Path(herd_source), pins)
    version = model['checked']([herd, '-version']).strip()
    if not version.startswith('7.58,') and version != '7.58':
        raise ValueError('herd executable version differs from pin')
    expected = catalog(tests)
    report = json.loads((out/'catalog.json').read_text())
    if [(r['test'], r['sha256'], r['status']) for r in expected] != [
            (r['test'], r['sha256'], r['status']) for r in report['cases']]:
        raise ValueError('campaign catalog differs from current pinned source')
    summary = runpy.run_path(str(HERE/'summarize.py'))['summarize']
    for row in report['cases']:
        if row['status'] != 'applicable':
            continue
        start = time.monotonic()
        test = tests/row['test']
        try:
            folder = out/row['name']
            row['rtl'] = summary(out/(row['name']+'-run'))
            c1 = json.loads((out/(row['name']+'-run')/'result.json').read_text())
            row['timing'] = c1['details']['timing']
            row['elf_sha256'] = {str(e['hart']): e['elf_sha256'] for e in
                                  json.loads((folder/'hart-images.json').read_text())['harts']}
            if row['rtl']['status'] != 'pass':
                row['outcome'] = dict(status='inconclusive', reason='RTL did not pass')
                continue
            spec = parse_text(test.read_text())
            observed = capture(out/row['name'], spec['projection'], row['sha256'])
            result = run_group(['nice', '-n', '10', herd, '-I', str(libdir), '-model',
                                str(libdir/'riscv.cat'), str(test)], timeout=120, capture=True)
            if result.returncode or result.timed_out:
                raise ValueError('herd execution failed or timed out')
            (out/row['name']/'herd.log').write_text(result.stdout)
            allowed = model['parse_states'](result.stdout)
            # RV64 register bit patterns include sign-extended load values.
            unsigned = lambda state: tuple(sorted((k, v & ((1 << 64)-1)) for k, v in state))
            allowed = {unsigned(state) for state in allowed}
            row['outcome'] = model['compare'](allowed, observed)
            row['observed'] = observed
            if row['outcome']['status'] == 'consistent' and 'negative_control' not in report:
                state = dict(observed['observations'][0]['state'])
                key = next(iter(state))
                impossible = 0
                seen = {dict(a)[key] for a in allowed}
                while impossible in seen:
                    impossible += 1
                state[key] = impossible
                planted = dict(harts=observed['harts'], complete=True,
                               observations=[dict(state=state, count=1)])
                rejected = model['compare'](allowed, planted)
                if rejected['status'] != 'mismatch':
                    raise ValueError('planted forbidden outcome was not rejected')
                report['negative_control'] = dict(test=row['test'], state=state,
                                                  status='mismatch', scope='planted outcome, not a core defect')
            row['herd_log_sha256'] = hashlib.sha256(result.stdout.encode()).hexdigest()
        except (ValueError, OSError) as exc:
            row['outcome'] = dict(status='inconclusive', reason=str(exc))
        finally:
            row['check_seconds'] = time.monotonic()-start
    report['outcome_counts'] = dict(Counter(r['outcome']['status'] for r in report['cases'] if 'outcome' in r))
    report['completion_counts'] = dict(Counter(r['rtl']['status'] for r in report['cases'] if 'rtl' in r))
    report['herd_version'] = version
    report['herd_executable_sha256'] = hashlib.sha256(Path(herd).read_bytes()).hexdigest()
    report['scope'] = 'one native outcome per applicable scalar test; unsupported cases listed'
    (out/'upstream-results.json').write_text(json.dumps(report, indent=2)+'\n')
    return report['outcome_counts']


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['prepare', 'summarize'])
    parser.add_argument('--tests', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--herd')
    parser.add_argument('--herd-source')
    args = parser.parse_args()
    print(prepare(args.tests, args.out) if args.action == 'prepare' else
          summarize(args.tests, args.out, args.herd, args.herd_source))
