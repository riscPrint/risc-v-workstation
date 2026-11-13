"""Convert real probes, fit training kernels, and score disjoint held-out ELFs."""
import json
from pathlib import Path
import subprocess
import sys
from rvw.ooo.evidence import calibrate

ROOT = Path(__file__).resolve().parents[3]
TRAIN = ('chain', 'multiply', 'memory')
HELD = ('independent', 'divide', 'branch')


def score(out, core):
    out = Path(out).resolve()
    dest = out/core
    mapping = {}
    if core == 'vexriscv':
        mapping['branches'] = dict(model_event='branches', rtl_event='branches', edge='retirement',
                                  unit='instructions', identity='conditional and direct/indirect jumps',
                                  family='control', region='whole-program')
    (dest/'event-map.json').write_text(json.dumps(mapping))
    samples = []
    for name in TRAIN+HELD:
        run = dest/name
        if core == 'vexriscv':
            subprocess.run([str(ROOT/'rvw/.venv/bin/rvw'),'probes','convert',str(run/'probe-events.jsonl'),
                            '--to','counts','--c1',str(run/'result.json'),'--c2',str(run/'rvfi.jsonl'),
                            '--out',str(run/'counts.json')],check=True)
        else:
            from rvw.ooo.evidence import digest
            (run/'counts.json').write_text(json.dumps(dict(counts={},c1_sha256=digest(run/'result.json'),
                                                        trace_sha256=digest(run/'rvfi.jsonl'))))
        samples.append(dict(id=name, split='training' if name in TRAIN else 'heldout',
                            elf=str(out/'elf'/name),trace=str(run/'rvfi.jsonl'),
                            c1=str(run/'result.json'),events=str(run/'counts.json')))
    plan = dest/'calibration-plan.json'
    plan.write_text(json.dumps(dict(schema='rvw.ooo-calibration-plan/1',
        config=str(ROOT/f'examples/{core}/rvw/arch/own.json'),event_map='event-map.json',samples=samples),indent=2))
    calibrate(plan,dest/'baseline.json')
    fp = dest/'fit-plan.json'
    fp.write_text(json.dumps(dict(schema='rvw.ooo-fit-plan/1',calibration_plan='calibration-plan.json',
                                 parameters={'frontend.fetch_latency':([3,5,7,9] if core == 'vexriscv' else [1,2,3,4]), 'branch_penalty':[1,3,5,7]})))
    with (dest/'fit-stdout.json').open('w') as output:
        subprocess.run(['nice','-n','10',str(ROOT/'rvw/.venv/bin/rvw'),
                        'arch','ooo-fit',str(fp),'--out',str(dest/'fit'),'--json'],
                       stdout=output,check=True)

if __name__ == '__main__':
    score(*sys.argv[1:])
