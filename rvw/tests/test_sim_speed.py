import json
from pathlib import Path

import pytest

from rvw.sim.speed import compare, evidence


def result(root, seconds=2, native='c', change=None):
    root.mkdir()
    obj = dict(schema='rvw.run/1', status='pass', core='fixture', config='preset',
               seed=1, max_cycles=2000000, mem_latency=0, cycles=1000000, instret=1,
               elf_sha256='a' * 64, rtl_sha256='b' * 64,
               tools={'native_build': {'sha256': native * 64}},
               details={'execution_s': seconds, 'model': {'rvfi': True}},
               artifacts={'rvfi_trace': 'rvfi.jsonl'})
    if change:
        change(obj)
    (root / 'result.json').write_text(json.dumps(obj))
    event = dict(order=0, cycle=1, mode=3, insn='0x13', pc='0x80000000', pc_next='0x80000004',
                 rs1=0, rs2=0, rd=0, rs1_rdata='0x0', rs2_rdata='0x0', rd_wdata='0x0',
                 mem_addr='0x0', mem_rdata='0x0', mem_wdata='0x0', mem_rmask=0, mem_wmask=0,
                 trap=False, intr=False, halt=False, mem_fault=False)
    events = [dict(schema='rvw.rvfi/1', xlen=64, isa='rv64i', core='fixture', config='preset', elf='test.elf', seed=1, elf_sha256='a' * 64), event,
              dict(event='end', cycle=1000000, status='pass')]
    (root / 'rvfi.jsonl').write_text(''.join(json.dumps(e) + '\n' for e in events))
    return root / 'result.json'


def pairs(tmp_path):
    return [(result(tmp_path / f'a{i}', 2), result(tmp_path / f'b{i}', 1, 'd')) for i in range(5)]


def test_equivalent_paired_bootstrap(tmp_path):
    data = pairs(tmp_path)
    report = compare(data, resamples=1000)
    assert report['speedup'] == 2
    assert report['speedup_ci95'] == [2, 2]
    assert report['retain'] is True
    assert report['pairs'][0]['baseline']['sim_khz'] == 500
    assert report == compare(data, resamples=1000)


def test_no_gain_is_not_retained(tmp_path):
    data = [(result(tmp_path / f'a{i}'), result(tmp_path / f'b{i}')) for i in range(5)]
    assert compare(data, resamples=1000)['retain'] is False


@pytest.mark.parametrize('change', [
    lambda o: o.update(status='timeout'), lambda o: o.update(inconclusive='capture missing'),
    lambda o: o.update(wall_clock_timeout=True), lambda o: o.update(elf_sha256=None),
    lambda o: o.update(cycles=0), lambda o: o.update(instret=True),
    lambda o: o.update(seed=None), lambda o: o.update(tools={}),
    lambda o: o['details'].update(concurrent=True),
    lambda o: o['details'].update(serial_rerun={'status': 'pass'}),
    lambda o: o['details'].update(execution_s=float('nan')),
    lambda o: o['details'].update(execution_s=0.1),
    lambda o: o.update(artifacts={}),
])
def test_missing_invalid_or_short_evidence_is_rejected(tmp_path, change):
    path = result(tmp_path / 'run', change=change)
    with pytest.raises(ValueError):
        evidence(path)


@pytest.mark.parametrize('mutation', ['truncate', 'status', 'cycle', 'instret', 'seed', 'effect'])
def test_changed_trace_cannot_earn_speedup(tmp_path, mutation):
    data = pairs(tmp_path)
    path = Path(data[-1][1]).parent / 'rvfi.jsonl'
    events = [json.loads(line) for line in path.read_text().splitlines()]
    if mutation == 'truncate':
        events.pop()
    elif mutation in ('cycle', 'status'):
        events[-1][mutation] = 99 if mutation == 'cycle' else 'fail'
    elif mutation == 'instret':
        events.pop(1)
    elif mutation == 'seed':
        events[0]['seed'] = 2
    else:
        events[1]['rd_wdata'] = '0x1'
    path.write_text(''.join(json.dumps(e) + '\n' for e in events))
    with pytest.raises(ValueError):
        compare(data, resamples=1000)


def test_duplicate_samples_changed_native_or_workload_rejected(tmp_path):
    data = pairs(tmp_path)
    with pytest.raises(ValueError, match='five'):
        compare(data[:4])
    with pytest.raises(ValueError, match='reused'):
        compare([data[0]] * 5)
    path = data[-1][1]
    obj = json.loads(path.read_text()); obj['tools']['native_build']['sha256'] = 'e' * 64
    path.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match='native build'):
        compare(data)
    obj['tools']['native_build']['sha256'] = 'd' * 64
    obj['config'] = 'other'; path.write_text(json.dumps(obj))
    with pytest.raises(ValueError, match='differ'):
        compare(data)


def test_dashboard_plots_speed_per_preset(tmp_path, monkeypatch):
    from types import SimpleNamespace as NS
    import importlib
    mod = importlib.import_module('rvw.farm.dashboard')
    monkeypatch.setattr(mod, 'read_index', lambda _: [{'path': str(tmp_path), 'run_id': 'one'}])
    monkeypatch.setattr(mod, 'find_results', lambda _: [NS(core='fixture', suite='long', config=p, tests=[
        NS(status='pass', conclusive=True, wall_s=2, metrics={'sim_khz': 10, 'sim_instructions_per_s': 100})])
        for p in ('small', 'large')])
    out = tmp_path / 'dashboard.html'
    mod.dashboard(tmp_path, out)
    for p in ('small', 'large'):
        for m in ('sim_khz', 'sim_instructions_per_s'):
            assert f'fixture / long / {p} / {m}' in out.read_text()
