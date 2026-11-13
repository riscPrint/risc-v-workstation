"""Fault campaign: sites from a design database, plans, classification and reports (fake adapter)."""
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from rvw.debug.hart import Asm
from rvw.fault import campaign, api
from rvw.results.schema import validate_results

ADAPTER = [sys.executable, str(Path(__file__).parent / 'fixtures/fault/adapter.py')]


def add(rd, rs1, rs2):
    return (rs2 << 20) | (rs1 << 15) | (rd << 7) | 0x33


def program(tmp_path):
    """x5 = 5+4+3+2+1, x8 logged to memory without a check, x9 guarded by parity, then ebreak."""
    words = [Asm.addi(5, 0, 0), Asm.addi(6, 0, 5), Asm.auipc(7, 1), Asm.addi(8, 0, 0x55), Asm.addi(9, 0, 7),
             add(5, 5, 6), Asm.addi(6, 6, -1), Asm.bne(6, 0, -8),
             Asm.sw(8, 7, 4), Asm.addi(9, 9, 1), Asm.EBREAK]
    path = tmp_path / 'prog.bin'
    path.write_bytes(Asm.words(*words))
    return path


def database(tmp_path):
    path = tmp_path / 'design.db'
    conn = sqlite3.connect(path)
    conn.executescript('''CREATE TABLE meta(key, value);
      INSERT INTO meta VALUES('schema', 'rvw.designdb/20');
      CREATE TABLE signals(id, path, width, kind, generated, pruned, clock_domain_id);''')
    rows = [(1, 'core.x5', 64, 'reg', 0, 0, 1), (2, 'core.x8', 64, 'reg', 0, 0, 1), (3, 'core.x9', 64, 'reg', 0, 0, 1),
            (4, 'core.x20', 64, 'reg', 0, 0, 1), (5, 'core.tmp', 8, 'reg', 1, 0, 1), (6, 'core.bus', 32, 'wire', 0, 0, 1),
            (7, 'core.gone', 4, 'reg', 0, 1, 1)]
    conn.executemany('INSERT INTO signals VALUES (?, ?, ?, ?, ?, ?, ?)', rows)
    conn.commit()
    conn.close()
    return path


def test_sites_from_design_database(tmp_path):
    db = database(tmp_path)
    found = campaign.sites(db)
    assert [s['path'] for s in found] == ['core.x20', 'core.x5', 'core.x8', 'core.x9']
    assert [s['path'] for s in campaign.sites(db, generated=True)][0] == 'core.tmp'
    assert [s['path'] for s in campaign.sites(db, include=['core.x[58]'])] == ['core.x5', 'core.x8']
    assert campaign.sites(db, exclude=['core.x*']) == []
    bad = tmp_path / 'bad.db'
    sqlite3.connect(bad).executescript("CREATE TABLE meta(key, value); INSERT INTO meta VALUES('schema','x');")
    with pytest.raises(ValueError):
        campaign.sites(bad)


def test_plan_is_seeded_and_counts_population(tmp_path):
    found = campaign.sites(database(tmp_path))
    a = campaign.plan(found, samples=50, seed=3, window=(0, 20))
    b = campaign.plan(found, samples=50, seed=3, window=(0, 20))
    assert a['faults'] == b['faults'] and len(a['faults']) == 50 and a['sampling'] == 'uniform-random'
    assert a['population_total'] == 3 * 256 * 20
    assert len({(f['kind'], f['site'], f['bit'], f['cycle']) for f in a['faults']}) == 50
    tiny = campaign.plan([{'path': 'core.x5', 'width': 2}], kinds=('flip',), window=(0, 3), samples=100)
    assert tiny['sampling'] == 'exhaustive' and len(tiny['faults']) == 6
    with pytest.raises(ValueError):
        campaign.plan(found, kinds=('melt',))


def fault(kind, site, bit, cycle, duration=None):
    f = {'id': f'{kind}-{site}-{bit}-{cycle}', 'kind': kind, 'site': site, 'bit': bit, 'cycle': cycle}
    if duration is not None:
        f['duration'] = duration
    return f


def test_classification(tmp_path):
    elf = program(tmp_path)
    plan_data = {'schema': campaign.PLAN_SCHEMA, 'seed': 0, 'population_total': 100, 'sampling': 'explicit',
                 'faults': [fault('flip', 'core.x5', 3, 9),       # corrupts the checked sum: detected by self-test
                            fault('flip', 'core.x8', 0, 6),       # logged value: silent corruption
                            fault('flip', 'core.x20', 7, 4),      # unused register: safe
                            fault('stuck1', 'core.x9', 2, 1),     # parity checker: detected
                            fault('flip', 'core.x5', 1, 400),     # never reached: not injected
                            fault('flip', 'core.pc', 1, 3)]}      # unknown site: not injected
    detections = tmp_path / 'detections.json'
    detections.write_text(json.dumps({'mechanisms': ['parity_x9'], 'status': {'fail': 'self-test'}}))
    plan_path = tmp_path / 'plan.json'
    plan_path.write_text(json.dumps(plan_data))
    summary = api.run(plan_path, ADAPTER, elf, tmp_path / 'out', jobs=2, detections=detections)
    outcomes = {o['id']: o for o in json.loads((tmp_path / 'out/outcomes.json').read_text())}
    got = {k: v['classification'] for k, v in outcomes.items()}
    assert got == {'flip-core.x5-3-9': 'detected', 'flip-core.x8-0-6': 'silent_corruption',
                   'flip-core.x20-7-4': 'safe', 'stuck1-core.x9-2-1': 'detected',
                   'flip-core.x5-1-400': 'not_injected', 'flip-core.pc-1-3': 'not_injected'}
    assert outcomes['stuck1-core.x9-2-1']['evidence']['detected_by'] == ['parity_x9']
    assert outcomes['flip-core.x5-3-9']['evidence']['detected_by'] == ['self-test']
    assert summary['injected'] == 4 and summary['counts']['not_injected'] == 2
    assert summary['diagnostic_coverage'] == round(2 / 3, 4) and summary['diagnostic_coverage_95']
    assert 'no ISO 26262' in summary['scope']
    results = json.loads((tmp_path / 'out/results.json').read_text())
    assert not validate_results(results)
    statuses = {t['id']: t['status'] for t in results['tests']}
    assert statuses['flip-core.x8-0-6'] == 'fail' and statuses['flip-core.x20-7-4'] == 'pass'
    assert statuses['flip-core.pc-1-3'] == 'error'
    assert api.report(tmp_path / 'out')['counts'] == summary['counts']


def test_failing_golden_run_is_refused(tmp_path):
    elf = tmp_path / 'bad.bin'
    elf.write_bytes(Asm.words(Asm.addi(5, 0, 1), Asm.EBREAK))     # sum check fails
    plan_data = {'schema': campaign.PLAN_SCHEMA, 'seed': 0, 'population_total': 1, 'sampling': 'explicit',
                 'faults': [fault('flip', 'core.x5', 0, 0)]}
    plan_path = tmp_path / 'plan.json'
    plan_path.write_text(json.dumps(plan_data))
    with pytest.raises(ValueError, match='golden'):
        api.run(plan_path, ADAPTER, elf, tmp_path / 'out')


def test_adapter_without_confirmation_is_not_injected(tmp_path):
    c1 = {'status': 'pass', 'details': {}}
    assert campaign.classify(c1, False, [], tmp_path)[0] == 'not_injected'
    assert campaign.classify(None, True, [], tmp_path)[0] == 'timeout'
    c1 = {'status': 'timeout', 'details': {'fault': {'applied': True}}}
    assert campaign.classify(c1, False, [], tmp_path)[0] == 'timeout'
    assert campaign.classify(c1, False, [], tmp_path, watchdog=True)[0] == 'detected'
    c1 = {'status': 'pass', 'details': {'fault': {'applied': True}}, 'artifacts': {}}
    assert campaign.classify(c1, False, [], tmp_path)[0] == 'inconclusive'


def test_cli_plan_and_sites(tmp_path):
    import subprocess
    db = database(tmp_path)
    run = subprocess.run([sys.executable, '-m', 'rvw', 'fault', 'plan', '--db', str(db), '--samples', '10',
                          '--window', '0:30', '--out', str(tmp_path / 'p.json')], capture_output=True, text=True)
    assert run.returncode == 0, run.stderr
    assert len(json.loads((tmp_path / 'p.json').read_text())['faults']) == 10
