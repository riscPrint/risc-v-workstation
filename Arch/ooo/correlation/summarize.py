"""Publish compact measured correlation values without local source paths."""
import json
from pathlib import Path
import sys


def summarize(out, target):
    out = Path(out)
    results = {}
    for core in ('vexriscv','vexiiriscv'):
        directory = out/core
        baseline = json.loads((directory/'baseline.json').read_text())
        fitted = json.loads((directory/'fit/calibration.json').read_text())
        selection = json.loads((directory/'fit/report.json').read_text())
        rows = []
        for split in ('training','heldout'):
            for a,b in zip(baseline['samples'][split],fitted['samples'][split]):
                rows.append(dict(id=a['id'],split=split,instret=a['model']['instret'],
                    rtl_cycles=a['rtl_cycles'],rtl_ipc=a['rtl_ipc'],
                    baseline_cycles=a['model']['cycles'],baseline_ipc=a['model']['ipc'],
                    baseline_ipc_error_percent=a['ipc_error_percent'],fitted_cycles=b['model']['cycles'],
                    fitted_ipc=b['model']['ipc'],fitted_ipc_error_percent=b['ipc_error_percent'],
                    hashes=a['hashes'],rtl_events=a['events']))
        results[core] = dict(best=selection['best'],samples=rows,
            budgets=fitted['budgets'],baseline_engine_sha256=baseline['samples']['training'][0]['model']['engine_sha256'])
    Path(target).write_text(json.dumps(dict(schema='rvw.arch-rtl-correlation-sample/1',
        conditions=dict(seed=1,mem_latency=0,region='whole-program',
                        vexriscv_revision='a62c145aa042a5de874344e0a7683bd7c8c8c870',
                        vexriscv_core_sources='unchanged from baf7dc82f855eddaf5b0a20a6802c526f127e38a',
                        vexiiriscv_revision='9f70315deb3390b283995c5b8f1bd38215ecf52b',training=['chain','multiply','memory'],
                        heldout=['independent','divide','branch']),results=results,
        limits=['six small synthetic RV32IM programs; not application qualification',
                'one native run per program; repeatability is unmeasured',
                'VexiiRiscv has no SpinalProbes binding; its event map is empty',
                'the fit grid changes fetch delay and branch penalty only']),indent=2)+'\n')

if __name__ == '__main__':
    summarize(*sys.argv[1:])
