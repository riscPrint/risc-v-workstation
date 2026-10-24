#!/usr/bin/env python3
"""Real Verilator + SBY + MCY demo. Invoke under scripts/with-lock.sh boom."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys


def proof_plan(source, point_id):
    """The proof plan for the unreachable `state == 3` branch of tiny.sv. The harness instantiates
    `tiny`, which has no reset (state starts at zero), so the plan says so: `"reset": null`. The
    vacuity guard refuses a plan that leaves the reset unstated."""
    return {"sources": [str(source / 'tiny.sv')], "harness": str(source / 'harness.sv'),
            "top": "harness", "depth": 8, "reset": None,
            "assumptions": "No assumptions; no reset, state initializes to zero as in simulation.",
            "points": [{"point_id": point_id, "expression": "y == 5'd31",
                        "reason": "Output 31 occurs only in the state==3 branch; modulo-three state never reaches 3."}]}


def mutation_observations(result):
    """Keep the demo's measured MCY observations distinct from earned kills."""
    if result.get('status') != 'inconclusive' or result.get('cause') != 'input_not_captured:mcy_dependencies':
        raise ValueError('mutation demo requires an explicit incomplete-dependency result')
    if any(result['counts'][state] for state in ('killed', 'survived', 'equivalent', 'control')):
        raise ValueError('incomplete mutation dependencies cannot establish earned outcomes')
    return result['observed_counts']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    source = Path(__file__).resolve().parent
    cli = [sys.executable, '-m', 'rvw.cli', 'cov']

    def command(argv, name, cwd=None, allowed=(0,)):
        with (out / f'{name}.log').open('w') as log:
            completed = subprocess.run([str(a) for a in argv], stdout=log, stderr=subprocess.STDOUT, cwd=cwd)
            if completed.returncode not in allowed:
                raise subprocess.CalledProcessError(completed.returncode, argv)

    def cov(name, *argv):
        target = out / f'{name}.json'
        command([*cli, *argv, '--json', '--out', target], name,
                allowed=(0, 3) if argv[0] == 'mutate' else (0,))
        return json.loads(target.read_text())

    command(['verilator', '--cc', '--exe', '--build', '-j', '2', '--coverage', '-Wno-fatal',
             '--top-module', 'tiny', '--Mdir', out / 'obj', source / 'tiny.sv', source / 'sim.cpp'], 'build')
    for test in ('0', '1'):
        command([out / 'obj/Vtiny', test, out / f'{test}.dat'], f'sim-{test}')
    data = cov('merged', 'merge', f'zero={out / "0.dat"}', f'one={out / "1.dat"}',
               '--dat', out / 'merged.dat')
    report = cov('report', 'report', out / 'merged.json', '--annotate', out / 'annotations')
    ranking = cov('rank', 'rank', out / 'merged.json', '--exact')
    line = next(n for n, text in enumerate((source / 'tiny.sv').read_text().splitlines(), 1)
                if 'if (state == 3)' in text)
    point = next(p for p in data['points'] if p['fields'].get('l') == str(line) and p['fields'].get('o') == 'if')
    config = proof_plan(source, point['id'])
    (out / 'proof-plan.json').write_text(json.dumps(config, indent=2))
    proof = cov('exclusions', 'prove', out / 'merged.json', '--config', out / 'proof-plan.json',
                '--work-dir', out / 'proof')
    assert proof['points'][0]['unreachable'], proof
    excluded = cov('report-excluded', 'report', out / 'merged.json', '--exclusions', out / 'exclusions.json')
    mutation_dir = out / 'mcy'
    mutation_dir.mkdir()
    for name in ('tiny.sv', 'tb.sv', 'config.mcy', 'test_sim.sh', 'baseline.sh'):
        shutil.copyfile(source / name, mutation_dir / name)
    mutation = cov('mutation', 'mutate', mutation_dir, '--run', '--baseline', mutation_dir / 'baseline.sh',
                   '--timeout', '120', '--jobs', '1')
    observed = mutation_observations(mutation)
    assert observed['killed'] and observed['survived'], observed
    assert not observed['pending'] and not observed['error'], observed
    result = {"schema": "rvw.coverage-demo/1", "kind": "real-tool-small-design",
              "source_sha256": hashlib.sha256((source / 'tiny.sv').read_bytes()).hexdigest(),
              "tools": {tool: subprocess.run([tool, '--version'], capture_output=True, text=True).stdout.strip()
                        for tool in ('verilator', 'yosys', 'sby')},
              "code": report['summary'], "after_exclusion": excluded['summary'], "selected": ranking['selected'],
              "formal": {mode: job['status'] for mode, job in proof['points'][0]['jobs'].items()},
              "mutation": {"status": mutation['status'], "observed_counts": observed}, "artifacts": str(out),
              "note": "Small Verilog design only. MCY observations do not establish earned kills or equivalence."}
    (out / 'summary.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
