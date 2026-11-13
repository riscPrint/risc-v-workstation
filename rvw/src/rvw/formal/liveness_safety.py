"""Feed SVA progress monitors to the existing finite-state RTL L2S runner."""
from argparse import Namespace
import contextlib
import json
from pathlib import Path
import shutil

from rvw.common.proc import run_group
from . import common, liveness_app


def run(out, top, rows, capture, args):
    reset = getattr(args, 'reset', None)
    if not reset:
        raise ValueError('l2s needs --reset with an active-high input port')
    common.check_ident('reset', reset)
    if not getattr(args, 'run', False):
        raise ValueError('l2s requires --run; native model export is part of execution')
    live = [row for row in rows if row['kind'] == 'live']
    if not live:
        return dict(observation='no_checks', jobs=[])
    if not shutil.which('yosys') or not shutil.which('sby'):
        return dict(observation='missing_tool', jobs=[])
    yosys = capture.tool('yosys')
    flat, metadata = out / 'progress.v', out / 'progress.json'
    script = '; '.join([
        'read_verilog -formal -sv ' + json.dumps(str(out / 'lowered.sv')),
        f'prep -top {top} -flatten', 'memory_map', 'opt_clean', f'select -module {top}',
        'expose ' + ' '.join('w:' + row['wire'] for row in rows), 'select *',
        'write_json ' + json.dumps(str(metadata)),
        'write_verilog -noattr ' + json.dumps(str(flat))])
    with (out / 'l2s-export.log').open('w') as log:
        exported = run_group(['nice','-n','10',str(yosys.path),'-Q','-T','-p',script],
                             stdout=log,stderr=log,timeout=args.timeout)
    if exported.timed_out or exported.returncode:
        return dict(observation='timeout' if exported.timed_out else 'error', jobs=[], log='l2s-export.log')
    module = json.loads(metadata.read_text())['modules'][top]
    # The reused engine snapshots bit aliases. Limit this adapter to canonical
    # ranges until that engine qualifies other packed index orientations.
    if any(net.get('offset',0) or net.get('upto',0) for net in module['netnames'].values()):
        raise ValueError('l2s adapter needs zero-based descending net ranges')
    if reset not in module['ports'] or module['ports'][reset]['direction'] != 'input' or len(module['ports'][reset]['bits']) != 1:
        raise ValueError('l2s reset must be a scalar input')
    fairness = [row['wire'] for row in rows if row['kind'] == 'fair']
    jobs = []
    for index, row in enumerate(live):
        directory = out / f'l2s-{index}'
        if directory.exists():
            shutil.rmtree(directory)
        manifest = out / f'l2s-{index}.json'
        common.write_json(manifest, dict(schema='rvw.liveness-app/1', top=top, clock=row['clock'], reset=reset,
                                        verilog=[str(flat)], request='1', response=row['wire'], fairness=fairness))
        mode = getattr(args,'mode','prove')
        engine = getattr(args,'engine',None) or ('abc:pdr' if mode == 'prove' else 'smtbmc:yices')
        child = Namespace(manifest=str(manifest), out=str(directory), depth=getattr(args,'depth',20),
                          engine=engine, timeout=args.timeout,
                          mode=mode, json=True)
        with (out / f'l2s-{index}.log').open('w') as log, contextlib.redirect_stdout(log):
            liveness_app.run(child)
        data = json.loads((directory / 'result.json').read_text())
        jobs.append(dict(id=row['id'], status=data['status'], proof_kind=data['proof_kind'],
                         state_bits=data['state_bits'], result=f'l2s-{index}/result.json',
                         fairness=data['fairness'], limits=data['limits']))
    statuses = {job['status'] for job in jobs}
    return dict(observation='FAIL' if 'fail' in statuses else 'PASS' if statuses == {'pass'} else 'unknown', jobs=jobs)
