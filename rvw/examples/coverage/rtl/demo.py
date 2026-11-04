"""Small native RTL sampler. Run under scripts/with-lock.sh boom (no core used)."""
import argparse
import json
from pathlib import Path
from hashlib import sha256
from rvw.common.proc import run_group
from rvw.cov.rtl import identity, sample

p = argparse.ArgumentParser()
p.add_argument('out', type=Path)
a = p.parse_args()
a.out = a.out.resolve()
a.out.mkdir(exist_ok=False, parents=True)
here = Path(__file__).resolve().parent
plan = {'schema': 'rvw.rtl-plan/1', 'design': sha256((here / 'tiny.sv').read_bytes()).hexdigest(),
        'clock': {'signal': 'TOP.clk', 'edge': 'rising', 'sampling': 'pre-edge'},
        'reset': {'signal': 'TOP.reset', 'active': 1, 'rule': 'disable-clear'},
        'signals': {n: {'width': w, 'type': t, 'scala': None} for n, w, t in [
            ('TOP.clk', 1, 'Bool'), ('TOP.reset', 1, 'Bool'), ('TOP.state', 2, 'UInt(2 bits)')]},
        'bins': [{'id': f'state.{i}', 'kind': 'state', 'domain': 'structural', 'when': {'TOP.state': [i]}}
                 for i in range(4)] + [{'id': 'idle-active', 'kind': 'transition', 'domain': 'structural',
                     'from': {'TOP.state': [0]}, 'when': {'TOP.state': [1]}}],
        'sequences': [{'id': 'round-trip', 'domain': 'structural', 'steps': [
            {'when': {'TOP.state': [0]}}, {'when': {'TOP.state': [1]}, 'delay': [1, 2]},
            {'when': {'TOP.state': [0]}, 'delay': [2, 2]}]}]}
(a.out / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
with (a.out / 'build.log').open('w') as log:
    r = run_group(['verilator', '--cc', '--exe', '--build', '-j', '2', '--coverage-line', '--coverage-fsm',
                   '-Wno-fatal', '--top-module', 'RtlTiny', '--Mdir', str(a.out / 'obj'),
                   str(here / 'tiny.sv'), str(here / 'sample.cpp')], stdout=log, stderr=log, timeout=120)
    if r.returncode:
        raise SystemExit(f'build failed; see {a.out / "build.log"}')
r = run_group([str(a.out / 'obj/VRtlTiny'), str(a.out / 'samples.jsonl'), identity(plan), plan['design'],
               str(a.out / 'coverage.dat')], timeout=30)
if r.returncode:
    raise SystemExit('sample simulation failed')
result = sample(a.out / 'plan.json', [a.out / 'samples.jsonl'])
(a.out / 'report.json').write_text(json.dumps(result, indent=2) + '\n')
assert result['observed_bins'] == 4
assert result['bins'][3]['observation'] == 'unobserved'
assert result['sequences'][0]['completed'] > 0
print(json.dumps({'observed_bins': result['observed_bins'], 'denominator': result['denominator'],
                  'sequences': result['sequences']}))
