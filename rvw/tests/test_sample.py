import json
from pathlib import Path
import pytest
from rvw.sample.flow import aggregate, compare
from rvw.csim.simpoint import choose

pytestmark = pytest.mark.fast


def test_weight_cpi_not_ipc():
    points = [dict(status='matched', point={'weight':.5}, cpi=c) for c in (1,3)]
    assert aggregate(points)['weighted_ipc'] == .5
    points[0]['status'] = 'excluded'
    r = aggregate(points)
    assert r['status'] == 'inconclusive' and r['weighted_ipc'] is None
    assert r['covered_weight'] == .5


def test_single_interval_finite_bic(tmp_path):
    t = tmp_path/'trace'
    t.write_text('rvw.csim-trace/1\nB 2 100 cond 1 100 4\nEND 4\n')
    r = choose(t, 4)
    assert r['points'][0]['weight'] == 1
    json.dumps(r, allow_nan=False)


def test_compare_complete_and_mismatch(tmp_path, monkeypatch):
    import rvw.sample.flow as flow
    rows = [dict(pc=0, pc_next=4, insn=19, mode=3, rd=0, mem_rmask=0, mem_wmask=0, cycle=c) for c in (10,12,17)]
    class Parser:
        multihart = False
        state = True
        def __init__(self, path): pass
        def __iter__(self): return iter(rows+[dict(event='end', status='pass')])
        def close(self): pass
    monkeypatch.setattr(flow, 'Trace', Parser)
    expected = [dict(r) for r in rows]
    r = compare('unused', expected, 1, 2)
    assert r['cycles'] == 5 and r['ipc'] == .2
    expected[2]['pc'] = 4
    with pytest.raises(ValueError, match='mismatch'):
        compare('unused', expected, 1, 2)


def test_zero_capture(monkeypatch):
    from rvw.sim.spike_bootstrap import capture
    from types import SimpleNamespace
    mapping = json.loads((Path(__file__).parents[2]/'examples/vexriscv/rvw/bootstrap-profile.json').read_text())
    class Model:
        platform = SimpleNamespace(xlen=32, isa='rv32im_zicsr_zifencei', mmio=[], ram=[(0x80000000,8)], reset_pc=0x80000000)
        regs = [0]*32
        def csr_snapshot(self, names): return {k:0 for k in names}
        def read_physical(self, a): return 0
    assert capture(Model(), mapping, instructions=0)['pc'] == 0x80000000


def test_resume_checks_inputs(tmp_path, monkeypatch):
    import rvw.sample.flow as flow
    for name in ('elf','platform','shim','mapping'):
        (tmp_path/name).write_text('{}')
    spec = dict(schema='rvw.sample-study/1', elf='elf', platform='platform', shim='shim',
                mapping='mapping', instructions=20, adapter=['unused'])
    manifest = tmp_path/'study.json'
    manifest.write_text(json.dumps(spec))
    def profile(spec, out):
        p = out/'profile.csim'
        p.write_text('rvw.csim-trace/1\nB 10 100 cond 1 100 4\nEND 20\n')
        return p
    monkeypatch.setattr(flow, 'profile', profile)
    calls = []
    def point(spec, work, point, warmup):
        calls.append(point)
        return dict(status='matched', point=point, cpi=2)
    monkeypatch.setattr(flow, 'run_point', point)
    result = flow.run(manifest, tmp_path/'run', interval=10, max_k=1)
    assert result['weighted_ipc'] == .5 and calls
    assert result['scope'] == 'profiled prefix' and not result['program_complete']
    (tmp_path/'elf').write_text('changed')
    with pytest.raises(ValueError, match='inputs changed'):
        flow.run(manifest, tmp_path/'run', interval=10, max_k=1)


def test_profile_stops_at_tohost(tmp_path, monkeypatch):
    from types import SimpleNamespace
    import rvw.sample.flow as flow
    class Model:
        platform=SimpleNamespace(xlen=32)
        elf=SimpleNamespace(symbols={'tohost':0x2000})
        def step(self):
            return dict(pc=0x1000,pc_next=0x1004,insn=19,rd=0,trap=False,intr=False,
                        halted=False,mem_wmask=15,mem_wdata=1,mem_addr=0x2000)
        def close(self): pass
    monkeypatch.setattr(flow,'reference',lambda *a:Model())
    result=flow.profile({'instructions':1000000},tmp_path)
    assert result.read_text().endswith('END 1\n')
    assert flow.profile_complete(result)
