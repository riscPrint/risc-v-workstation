"""Sample the VexTop fetch interface. This is not an ISA test."""
import argparse
import json
from hashlib import sha256
from pathlib import Path

from rvw.common.proc import run_group
from rvw.cov import captured
from rvw.cov.code import SourceMap, merge
from rvw.cov.rtl import identity, sample

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('rtl', type=Path)
parser.add_argument('hgldd', type=Path)
parser.add_argument('out', type=Path)
args = parser.parse_args()
rtl, hgldd, out = args.rtl.resolve(), args.hgldd.resolve(), args.out.resolve()
out.mkdir(exist_ok=False, parents=True)


@captured.command
def mapping():
    return dict(SourceMap(hgldd=[hgldd]).signals)


locations = mapping()
names = ['clk', 'reset', 'iBus_cmd_valid', 'iBus_cmd_ready', 'iBus_rsp_valid']
signals = {}
for name in names:
    location = locations.get(('VexTop', name))
    signals['TOP.' + name] = {
        'width': 1, 'type': 'Bool',
        'scala': {k: location[k] for k in ('file', 'line')} if location else None}
accepted = {'TOP.iBus_cmd_valid': [1], 'TOP.iBus_cmd_ready': [1]}
response = {'TOP.iBus_rsp_valid': [1]}
plan = {
    'schema': 'rvw.rtl-plan/1', 'design': sha256(rtl.read_bytes()).hexdigest(),
    'clock': {'signal': 'TOP.clk', 'edge': 'rising', 'sampling': 'pre-edge'},
    'reset': {'signal': 'TOP.reset', 'active': 1, 'rule': 'disable-clear'},
    'signals': signals,
    'bins': [{'id': name, 'kind': 'event', 'domain': 'speculative', 'when': predicate}
             for name, predicate in [
                 ('fetch-accepted', accepted),
                 ('fetch-stalled', {'TOP.iBus_cmd_valid': [1], 'TOP.iBus_cmd_ready': [0]}),
                 ('fetch-response', response)]],
    'sequences': [{'id': 'fetch-response-next', 'domain': 'speculative', 'steps': [
        {'when': accepted}, {'when': response, 'delay': [1, 1]}]}]}
(out / 'plan.json').write_text(json.dumps(plan, indent=2) + '\n')
with (out / 'build.log').open('w') as log:
    result = run_group([
        'verilator', '--cc', '--exe', '--build', '-j', '2', '--coverage-line',
        '--coverage-toggle', '--coverage-fsm', '-Wno-fatal', '--top-module', 'VexTop',
        '--Mdir', str(out / 'obj'), str(rtl), str(Path(__file__).with_name('sample.cpp'))],
        stdout=log, stderr=log, timeout=300)
    if result.returncode:
        raise SystemExit(f'build failed; see {out / "build.log"}')
result = run_group([
    str(out / 'obj/VVexTop'), str(out / 'samples.jsonl'), identity(plan), plan['design'],
    str(out / 'coverage.dat')], timeout=30)
if result.returncode:
    raise SystemExit('sample simulation failed')
result = sample(out / 'plan.json', [out / 'samples.jsonl'])
(out / 'events.json').write_text(json.dumps(result, indent=2) + '\n')
unmapped = merge([str(out / 'coverage.dat')])
mapped = merge([str(out / 'coverage.dat')], hgldd=[hgldd])
summary = {
    'events': [(x['id'], x['count']) for x in result['bins']],
    'sequences': result['sequences'], 'points': len(mapped['points']),
    'mapped_without_hgldd': sum(bool(p['scala']) for p in unmapped['points']),
    'mapped_with_hgldd': sum(bool(p['scala']) for p in mapped['points']),
    'coverage_types': sorted({p['fields'].get('t') for p in mapped['points']})}
(out / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n')
print(json.dumps(summary))
