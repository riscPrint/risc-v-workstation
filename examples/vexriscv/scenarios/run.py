#!/usr/bin/env python3
"""Run the two native CPU-backed scenario consumers and compare observations."""
import argparse
import hashlib
import json
import os
import re
import shutil
from pathlib import Path
import sys

from rvw.common.proc import run_group
from rvw.formal.scenario import check
from rvw.sim.cocotb import run as cocotb_run
from rvw.soc.model import load

ROOT = Path(__file__).resolve().parents[3]


def observations(out):
    planned = json.loads((out / 'baremetal-plan.json').read_text())
    operations = json.loads((out / 'operations.json').read_text())
    model = load(ROOT / 'SpinalSoc/examples/vex/soc.json')
    bases = {region['name']:region['base'] for region in model['regions']}
    records, starts = [], {}
    for line in (out / 'baremetal/apb.jsonl').read_text().splitlines():
        row = json.loads(line)
        if 'bus' not in row or row['bus'] in ('ram','finisher'):
            continue
        bus = row['bus']
        if row['psel'] and not row['penable']:
            starts[bus] = row['cycle']
        if not (row['psel'] and row['penable'] and row['pready']):
            continue
        if row['pslverr'] or len(records) >= len(operations):
            raise ValueError('unexpected or failed APB transfer')
        action = operations[len(records)]
        if bases[bus] + row['paddr'] != action['address'] or bool(row['pwrite']) != (action['operation']=='write32'):
            raise ValueError('CPU APB transfer does not match the compiled action')
        value = row['pwdata'] if row['pwrite'] else row['prdata']
        records.append(dict(id=action['id'], operation=action['operation'], start=starts.pop(bus,row['cycle']),
                            end=row['cycle']+1, outputs={'value':value}, inputs={}, data={}))
    result = dict(schema='rvw.scenario-observation/1', plan_id=planned['plan_id'], backend=planned['backend'],
                  unit=planned['unit'], actions=records)
    (out / 'baremetal-observations.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def run(action, out):
    out = Path(out).resolve()
    if action == 'baremetal':
        classpath = ROOT / 'SpinalSoc/target/streams/runtime/fullClasspath/_global/streams/export'
        env = dict(os.environ, RVW_SOC_CLASSPATH=classpath.read_text().strip())
        with (out / 'baremetal-launch.log').open('w') as log:
            result = run_group([str(ROOT/'scripts/with-lock.sh'),'vex-sva','nice','-n','10',sys.executable,
                               str(ROOT/'SpinalSoc/examples/vex/adapter.py'),'run','--elf',str(out/'program.elf'),
                               '--out',str(out/'baremetal'),'--max-cycles','20000','--json'],
                               cwd=ROOT, env=env, stdout=log, stderr=log, timeout=150)
        if result.returncode:
            raise RuntimeError('native SoC program failed; see baremetal-launch.log')
        return observations(out)
    if action == 'pyuvm':
        # The Spinal library emits an implicit narrowing after an address shift.
        # Make that existing Verilog assignment conversion explicit. Keep every
        # bit and every assertion unchanged; do not suppress lint diagnostics.
        normalized = out / 'pyuvm-rtl'
        normalized.mkdir()
        sources = []
        images = {}
        for image in sorted((out/'rtl').glob('*.bin')):
            target = normalized / image.name
            shutil.copyfile(image, target)
            images[image.name] = hashlib.sha256(target.read_bytes()).hexdigest()
        casts = 0
        for path in sorted((out/'rtl').glob('*.v')):
            text = path.read_text()
            def module_cast(match):
                nonlocal casts
                body = match[0]
                widths = {name:abs(int(high)-int(low))+1 for high,low,name in
                          re.findall(r'wire\s*\[(\d+):(\d+)\]\s+(\w+)\s*;',body)}
                def assignment(row):
                    nonlocal casts
                    if row[1] not in widths:
                        return row[0]
                    casts += 1
                    return f"assign {row[1]} = {widths[row[1]]}'({row[2]});"
                return re.sub(r'assign\s+(\w+)\s*=\s*([^;]*>>>[^;]*);', assignment, body)
            text = re.sub(r'\bmodule\b.*?\bendmodule\b', module_cast, text, flags=re.S)
            def memory_path(match):
                name = match[2]
                if name not in images:
                    raise ValueError('missing generated memory image: ' + name)
                return match[1] + '"' + str(normalized / name) + '"'
            text = re.sub(r'(\$readmem[hb]\s*\(\s*)"([^"]+)"', memory_path, text)
            target = normalized / (path.stem + '.sv')
            target.write_text(text)
            sources.append(str(target))
        (out/'rtl-normalization.json').write_text(json.dumps(dict(explicit_shift_assignment_casts=casts, memory_sha256=images,
            scope='make the existing LHS width conversion explicit; no changed bits or disabled checks'))+'\n')
        manifest = dict(schema='rvw.cocotb/1' ,name='scenario_vex_soc',backend='verilator',top='ComposedSoc',
            sources=sources,test_module='test_scenario',
            python_paths=[str(out)],requires=['clock','timer'],clock=dict(signal='clk',period_ns=10),
            reset=dict(signal='reset',active=1,cycles=8))
        (out/'bench.json').write_text(json.dumps(manifest,indent=2)+'\n')
        result = cocotb_run(out/'bench.json', out/'pyuvm', seed=31, timeout=150)
        if any(hashlib.sha256((normalized/name).read_bytes()).hexdigest()!=checksum for name,checksum in images.items()):
            raise RuntimeError('memory image changed during native execution')
        if any(row['status']!='pass' for row in result['tests']):
            raise RuntimeError('native pyuvm test failed; see pyuvm/run.log')
        return result
    checks = {}
    values = {}
    for backend in ('baremetal','pyuvm'):
        planned = json.loads((out/(backend+'-plan.json')).read_text())
        actual = json.loads((out/(backend+'-observations.json')).read_text())
        checks[backend] = check(planned, actual)
        values[backend] = {row['id']:row['outputs'] for row in actual['actions']}
    result = dict(status='match' if all(c['status']=='match' for c in checks.values())
                  and values['baremetal']==values['pyuvm'] else 'mismatch', checks=checks,
                  scope='same real VexRiscv SoC CPU image; two observation consumers, not independent stimulus backends')
    (out/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    if result['status']!='match':
        raise RuntimeError('scenario observations differ')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['baremetal','pyuvm','check'])
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    print(json.dumps(run(args.action,args.out)))
