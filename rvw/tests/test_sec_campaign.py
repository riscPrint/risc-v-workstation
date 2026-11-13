"""Campaign loop with a fake adapter: divide latency depends on the secret."""
import json
import random
import sys
import pytest
from rvw.sec import campaign

pytestmark = pytest.mark.fast

ADAPTER = r'''
import json, sys
from pathlib import Path
req = json.loads(Path(sys.argv[1]).read_text()); out = Path(sys.argv[2])
rows = [dict(pc=hex(0x80000000+4*i), pc_next=hex(0x80000004+4*i), insn='0x13', rd_wdata='0x0', mem_addr='0x0',
             mem_rdata='0x0', mem_wdata='0x0', rs1=0, rs2=0, rs1_rdata='0x0', rs2_rdata='0x0', order=i, cycle=i,
             mode=3, rd=0, mem_rmask=0, mem_wmask=0, trap=False, intr=False, halt=False, mem_fault=False)
        for i, line in enumerate(l for l in req['program'] if not l.endswith(':'))]
head = dict(schema='rvw.rvfi/1', xlen=32, isa='rv32im', core='fake', config='x', elf='x')
text = '\n'.join(json.dumps(x) for x in [head] + rows + [dict(event='end', cycle=len(rows), status='pass')]) + '\n'
(out/'ref.jsonl').write_text(text); (out/'rtl.jsonl').write_text(text)
lat = [1 + (req['secret']['x6'] % 7 if l.split()[0] in ('div', 'rem') else 0) for l in req['program'] if not l.endswith(':')]
(out/'response.json').write_text(json.dumps(dict(complete=True, reset_complete=True, reference_c2='ref.jsonl',
    rtl_c2='rtl.jsonl', observations=dict(cycles=sum(lat), retire_cycles=lat))))
'''


def manifest(tmp_path, **extra):
    (tmp_path/'adapter.py').write_text(ADAPTER)
    m = dict(contracts=['constant-time'], observations=['cycles', 'retire_cycles'], seed=3,
             adapter_command=[sys.executable, str(tmp_path/'adapter.py'), '{request}', '{out}'],
             budget=dict(pairs=8, seconds=600), classes=['alu', 'div'], length=[2, 4], minimize_runs=10)
    m.update(extra)
    path = tmp_path/'campaign.json'; path.write_text(json.dumps(m))
    return path


def test_campaign_finds_reduces_and_deduplicates(tmp_path):
    r = campaign.run(manifest(tmp_path), tmp_path/'out')
    assert r['status'] == 'violation' and r['pairs'] == 8
    sigs = {f['signature'] for f in r['findings']}
    assert all(('div' in s or 'rem' in s) for s in sigs)
    assert all(f['contracts'] == ['constant-time'] for f in r['findings'])
    # Reduced witnesses keep only the instructions the leak needs.
    assert all(len(f['program']) == 1 for f in r['findings'])
    assert sum(f['count'] for f in r['findings']) == r['statuses']['violation']
    results = json.loads((tmp_path/'out/results.json').read_text())
    assert {t['status'] for t in results['tests']} == {'fail'}
    assert '| Signature |' in (tmp_path/'out/report.md').read_text()


def test_campaign_resumes_within_budget(tmp_path):
    path = manifest(tmp_path, classes=['alu'])
    first = campaign.run(path, tmp_path/'out')
    assert first['status'] == 'no_leak_observed' and first['pairs'] == 8
    data = json.loads(path.read_text()); data['budget']['pairs'] = 11; path.write_text(json.dumps(data))
    second = campaign.run(path, tmp_path/'out', resume=True)
    assert second['pairs'] == 11 and second['coverage_keys'] >= first['coverage_keys']
    results = json.loads((tmp_path/'out/results.json').read_text())
    assert results['tests'][0]['status'] == 'pass'
    with pytest.raises(FileExistsError):
        campaign.run(path, tmp_path/'out')


def test_grammar_keeps_secrets_out_of_addresses_and_branches():
    rng = random.Random(1)
    for _ in range(200):
        for line in campaign.generate(rng, list(campaign.GRAMMAR), 6):
            op = line.split()[0]
            if op in campaign.GRAMMAR['load'] or op in campaign.GRAMMAR['branch']:
                assert 'x6' not in line and 'x7' not in line
            if op in campaign.GRAMMAR['store']:
                assert line.endswith('(x30)')
    program = campaign.generate(rng, ['branch'], 3)
    assert sum(len(b) for b in campaign.blocks(program)) == len(program)
    assert all(b[0].split()[0] in campaign.GRAMMAR['branch'] and b[-1].endswith(':') for b in campaign.blocks(program))
    a, b = campaign.secret_pair(random.Random(2))
    assert a != b and set(a) == {'x6', 'x7'}


def test_signature_ignores_operands():
    one = campaign.signature(['remu x13, x6, x7'], ['cycles'])
    two = campaign.signature(['remu x9, x7, x6'], ['cycles'])
    assert one == two and one[0] == 'remu|cycles'


def test_clean_campaign_needs_enough_eligible_pairs(tmp_path):
    state = dict(signatures={}, statuses={'no_leak_observed': 1, 'ineligible': 7}, pairs=8, seconds=1.0,
                 coverage=[], corpus=[], errors=[])
    (tmp_path/'out').mkdir()
    r = campaign.finish(tmp_path/'out', state, {}, 8, 600)
    assert (r['status'], r['eligible_pairs'], r['min_eligible_pairs'], r['complete']) == ('inconclusive', 1, 4, False)
    results = json.loads((tmp_path/'out/results.json').read_text())
    assert results['tests'][0]['status'] == 'error' and 'minimum 4' in results['tests'][0]['inconclusive']
    state['statuses'] = {'no_leak_observed': 4, 'ineligible': 4}
    assert campaign.finish(tmp_path/'out', state, {}, 8, 600)['status'] == 'no_leak_observed'
    state['statuses'] = {'no_leak_observed': 1, 'ineligible': 7}
    assert campaign.finish(tmp_path/'out', state, {'min_eligible_fraction': 0.1}, 8, 600)['status'] == 'no_leak_observed'
