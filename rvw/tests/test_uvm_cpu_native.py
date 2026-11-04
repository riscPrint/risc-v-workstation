"""Opt-in native C1 replay and field-by-field corruption probes."""
import json
import os
from pathlib import Path
import pytest
from rvw.common.proc import run_group
from rvw.results import load_results
from rvw.sim.uvm_cpu import run, COLUMNS

pytestmark = pytest.mark.skipif(not os.environ.get('RVW_UVM_CPU_RUN'),
                                reason='set RVW_UVM_CPU_RUN to a completed scalar C1 run')


def test_native_c1_dpi_and_corruption(tmp_path):
    c1dir = Path(os.environ['RVW_UVM_CPU_RUN'])
    c1 = json.loads((c1dir/'result.json').read_text())
    out = tmp_path/'cpu'
    report = run(out,run_dir=c1dir,elf=Path(c1['elf']),
                 platform=Path(os.environ['RVW_UVM_CPU_PLATFORM']),
                 archive=Path(os.environ['RVW_UVM_ARCHIVE']),
                 verilator=os.environ.get('RVW_UVM_VERILATOR','verilator'))
    assert len(report['tests'])==2
    assert all(row['status']=='pass' for row in report['tests']), report
    assert all(row.conclusive for row in load_results(out).tests)
    lines = (out/'records.txt').read_text().splitlines()
    rows = [[int(v,16) for v in line.split()] for line in lines[1:]]
    # Select observations in which the value is meaningful. Do not test ignored lanes.
    for field in COLUMNS[:13] + ['rs1_rdata','rs2_rdata']:
        index = COLUMNS.index(field)
        candidates = range(len(rows))
        if field=='rd_wdata':
            candidates = [i for i,r in enumerate(rows) if r[4]]
        elif field in ('mem_addr','mem_rdata','mem_wdata'):
            mask_index = 8 if field=='mem_wdata' else 7
            candidates = [i for i,r in enumerate(rows) if r[mask_index]]
        assert candidates, f'fixture lacks {field}'
        selected = next(iter(candidates))
        changed = [r[:] for r in rows]
        bit = 1
        if field in ('mem_rdata','mem_wdata'):
            lanes = changed[selected][7 if field=='mem_rdata' else 8]
            bit = 1 << (8*((lanes & -lanes).bit_length()-1))
        changed[selected][index] ^= bit
        path = out/f'bad-{field}.txt'
        path.write_text(str(len(rows))+'\n'+''.join(' '.join(f'{v:x}' for v in r)+'\n' for r in changed))
        result = run_group([str(out/'build/Vtop'),f'+records={path}'],capture=True,timeout=30,cwd=out)
        assert not result.timed_out
        assert result.returncode != 0
        assert '[SPIKE_MISMATCH]' in result.stdout + result.stderr, (field,result)
        assert 'RVW_CPU_DONE' not in result.stdout + result.stderr
