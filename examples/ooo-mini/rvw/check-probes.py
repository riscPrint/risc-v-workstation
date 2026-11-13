#!/usr/bin/env python3
"""Run the fixed suites with probes, then qualify three project-owned goals."""
import json
import os
from pathlib import Path
import subprocess
from rvw.cosim.elf import Elf

project = Path(__file__).resolve().parent.parent
out = project/'rvw/out'
rvw = str(Path(os.environ['RVW_HOME'])/'rvw/.venv/bin/rvw')


def compare(rows):
    from rvw.common.capture import Capture
    from rvw.cosim.spike import Spike, capture_shim
    from rvw.cosim.platform import Platform
    from rvw.cosim.checker import check
    from rvw.regress.commands.suite_cosim import matched
    from rvw.results import load_run
    home = Path(os.environ['RVW_HOME'])
    capture = Capture(out/'probe-reference-inputs')
    shim = capture_shim(capture, home/'Cosim/build/librvw_spike.so')
    platform = Platform.load('ooo-mini',capture.file(project/'rvw/platform.json').copy)
    for row in rows:
        run_dir = Path(row['out'])
        run = load_run(run_dir/'result.json')
        assert run.status == 'pass' and not run.why_inconclusive
        masked = run_dir.name.startswith('scheduled-wfi-') and run_dir.name.endswith('-0')
        for label,sync in [('strict',())]+([('irq',('irq',))] if masked else []):
            model = Spike(platform,capture.file(Path(row['elf'])).copy,shim=shim)
            try:
                report = check(capture.file(run_dir/'rvfi.jsonl').copy,model,platform,sync=sync)
            finally:
                model.close()
            (run_dir/f'comparison-{label}.json').write_text(json.dumps(report))
            if sync or not masked:
                assert matched(report,run,sync), (run_dir.name,report['status'])
            print(json.dumps(dict(test=run_dir.name,comparison=label,status=report['status'],
                                  synchronized=report.get('synchronized'))),flush=True)
    (capture.root/'receipt.json').write_text(json.dumps(capture.record()))


def qualify(runs):
    # The two wrong-path words immediately precede the recovered label.
    wrong_pc = Elf(out/'pmp/protection-speculative.elf').symbols['recovered']-8
    plans = {
      'irq-full-3': dict(bins=[dict(id='irq_full_rob',kind='custom',name='interrupt',
                                  fields=dict(occupancy=[8],cause=[0x80000003]))]),
      'protection-speculative': dict(bins=[
          dict(id='wrong_path_load_fault',kind='custom',name='speculative_fault',fields=dict(cause=[5],pc=[wrong_pc])),
          dict(id='load_fault_commit',kind='custom',name='protection_fault',fields=dict(cause=[5],privilege=[0])),
          dict(id='store_fault_commit',kind='custom',name='protection_fault',fields=dict(cause=[7],privilege=[0])),
          dict(id='control_recovery',kind='custom',name='flush_reason',fields=dict(reason=[2]))],
          sequences=[dict(id='wrong_path_fault_then_recovery',steps=['wrong_path_load_fault','control_recovery'],max_gap=40)]),
      'flush-chain': dict(bins=[
          dict(id='forward_before_recovery',kind='custom',name='forwarding',fields=dict(bytes=list(range(1,16)),pending_recovery=[1])),
          dict(id='control_recovery',kind='custom',name='flush_reason',fields=dict(reason=[2])),
          dict(id='close_flushes',kind='custom',name='recovery_spacing',fields=dict(gap=list(range(2,9)))),
          dict(id='consecutive_cycle_flushes',kind='custom',name='recovery_spacing',fields=dict(gap=[1]))],
          sequences=[dict(id='forward_then_recovery',steps=['forward_before_recovery','control_recovery'],max_gap=8)])}
    for name, plan in plans.items():
        run = runs/name
        header = json.loads((run/'probe-events.jsonl').read_text().splitlines()[0])
        plan.update(schema='rvw.probe-goals/1',design=header['identity']['rtl_sha256'])
        path = run/'goal-plan.json'
        path.write_text(json.dumps(plan))
        completed = subprocess.run([rvw,'cov','probe-goals','--result',str(run/'result.json'),
                                    '--plan',str(path),'--platform',str(project/'rvw/platform.json'),'--json'],
                                   capture_output=True,text=True)
        (run/'goal-report.json').write_text(completed.stdout)
        completed.check_returncode()
        report = json.loads(completed.stdout)
        assert all(b['count'] > 0 for b in report['bins'] if b['id'] != 'consecutive_cycle_flushes')
        assert all(s['completed'] > 0 for s in report['sequences'])
        print(json.dumps(dict(test=name,status=report['status'],bins=report['bins'],
                              sequences=report['sequences'],holes=report['holes'])),flush=True)


if __name__ == '__main__':
    rows = [json.loads(line) for line in (out/'coverage-jobs.jsonl').read_text().splitlines()]
    assert len(rows) == 306
    for row in rows:
        row['out'] = str(out/'probe-runs'/Path(row['out']).name)
        row.pop('coverage')
        row['probes'] = True
    full = dict(next(row for row in rows if Path(row['elf']).stem == 'precise-3'))
    full['out'] = str(out/'probe-runs/irq-full-3')
    full['irq-schedule'] = '1:0x0,32:0x8,20000:0x0'
    rows.append(full)
    manifest = out/'probe-jobs.jsonl'
    manifest.write_text(''.join(json.dumps(row)+'\n' for row in rows))
    subprocess.run([str(project/'rvw/run.sh'),'run-many','--manifest',str(manifest),
                    '--jobs','4','--wall-timeout','115','--json'],check=True)
    compare(rows)
    qualify(out/'probe-runs')
