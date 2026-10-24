#!/usr/bin/env python3
"""Report the BOOM example suite in one process; avoids reloading its large point database."""
import argparse
from collections import Counter
from itertools import zip_longest
import json
from pathlib import Path
import subprocess
import sys
import time

from rvw.cov import code
from rvw.cov.functional import functional
from rvw.results import load_results, load_run, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('suite', type=Path, help='C3 integer-coverage/small/results.json')
    parser.add_argument('--out', required=True, type=Path, help='fresh report directory')
    parser.add_argument('--expected-tests', type=int, default=67)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()
    start = time.monotonic()
    suite = args.suite.resolve()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    result = load_results(suite)
    runs = [(t, load_run(suite.parent / t.run).to_dict(), (suite.parent / t.run).parent) for t in result.tests]
    if len(runs) != args.expected_tests:
        raise ValueError(f'expected {args.expected_tests} tests, got {len(runs)}')
    for t, r, directory in runs:
        for artifact in ('coverage', 'rvfi_trace'):
            if artifact not in r['artifacts'] or not (directory / r['artifacts'][artifact]).is_file():
                raise ValueError(f'{t.id}: missing {artifact} artifact')
    source = runs[0][1]['source']
    scala = Path(source['core_repo']) / 'src/main/scala'
    print('Merging code coverage', file=sys.stderr, flush=True)
    data = code.merge([str(suite)], scala_root=scala)
    # A machine database need not be indented; stream it once, keeping the same schema.
    with (out / 'code.json').open('w') as stream:
        json.dump(data, stream, separators=(',', ':'))
        stream.write('\n')
    print('Cross-checking verilator_coverage', file=sys.stderr, flush=True)
    files = [str(directory / r['artifacts']['coverage']) for _, r, directory in runs]
    with (out / 'verilator-merge.log').open('w') as log:
        subprocess.run(['verilator_coverage', '--write', str(out / 'merged.dat'), *files], check=True,
                       stdout=log, stderr=subprocess.STDOUT)
    counts = code.read_counts(out / 'merged.dat')
    if counts != {p['id']: p['count'] for p in data['points']}:
        raise ValueError('merged counts disagree with verilator_coverage')
    del counts
    print('Reporting code coverage', file=sys.stderr, flush=True)
    report = code.report(data)
    write_json(out / 'report.json', report)
    print('Ranking tests', file=sys.stderr, flush=True)
    ranking = code.rank(data)
    write_json(out / 'rank.json', ranking)
    del data
    print('Reporting RVFI functional coverage', file=sys.stderr, flush=True)
    traces = [str(directory / r['artifacts']['rvfi_trace']) for _, r, directory in runs]
    fc = functional(traces, Path(__file__).parent / 'integer-plan.json')
    write_json(out / 'functional.json', fc)
    first, second = files[:2]
    decreases = increases = point_count = 0
    for a, b in zip_longest(code.iter_dat(first, metadata=False), code.iter_dat(second, metadata=False)):
        if a is None or b is None or a[0] != b[0]:
            raise ValueError('cannot compare per-test counters with different point order/universes')
        point_count += 1
        decreases += a[3] > b[3]
        increases += a[3] < b[3]
    counter_check = {"first": runs[0][0].id, "second": runs[1][0].id, "points": point_count,
                     "counters_decreased": decreases, "counters_increased": increases,
                     "independent_counters_observed": decreases > 0}
    least = sorted(({"module": n, **v} for n, v in report['modules'].items() if v['eligible'] >= 100),
                   key=lambda v: (v['percent'], v['module']))[:15]
    logic = []
    for module, kinds in report['module_types'].items():
        parts = [v for kind, v in kinds.items() if kind in ('line', 'branch')]
        eligible, hit = sum(v['eligible'] for v in parts), sum(v['hit'] for v in parts)
        if eligible >= 10:
            logic.append({"module": module, "eligible_line_branch_points": eligible,
                          "hit": hit, "percent": 100 * hit / eligible})
    logic.sort(key=lambda v: (v['percent'], v['module']))
    summary = {"schema": "rvw.coverage-boom-evidence/1", "core": "boom", "config": "small",
        "expected_tests": args.expected_tests, "collected_tests": len(runs),
        "status": dict(Counter(t.status for t, _, _ in runs)),
        "failures": [{"id": t.id, "status": t.status, "message": r.get('message'), "signature": t.signature}
                     for t, r, _ in runs if t.status != 'pass'],
        "source": source, "tools": runs[0][1]['tools'], "model": runs[0][1]['details']['model'],
        "coverage_tools_rev": subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
        "coverage": report['summary'], "coverage_types": report['types'],
        "unmapped_scala_points": report['unmapped_scala_points'], "scala_locations": len(report['scala']),
        "least_covered_modules_minimum_100_points": least,
        "least_covered_logic_units_minimum_10_line_branch_points": logic[:20],
        "selected_tests": ranking['selected'], "selection_algorithm": ranking['algorithm'],
        "counter_independence": counter_check, "rvfi_traces": len(traces), "rvfi_instruction_records": fc['retired'],
        "functional": {n: {"observed_bins": g['observed_bins'], "expected_bins": g['expected_bins'], "holes": g['holes']}
                       for n, g in fc['groups'].items()}, "unknown_instruction_encodings": fc['unknown_encodings'],
        "compiler_workaround": "RISCVSIM_COVERAGE=line,user; native FSM state/arc coverage is absent",
        "wall_s": time.monotonic() - start, "artifacts": str(out), "notes": report['warnings']}
    write_json(out / 'summary.json', summary)
    if args.json:
        json.dump(summary, sys.stdout, indent=2)
        print()
    else:
        print(json.dumps({k: summary[k] for k in ('status', 'coverage', 'scala_locations', 'rvfi_instruction_records', 'artifacts')}))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as error:
        print(json.dumps({"schema": "rvw.coverage-error/1", "error": str(error)}))
        raise SystemExit(2)
