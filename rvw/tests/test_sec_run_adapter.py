"""Fast tests of the C1-run case adapter. No simulator or compiler is needed."""
import json
import pytest
from rvw.sec import run_adapter, spec_suite

pytestmark = pytest.mark.fast


def test_binding_and_run_command(tmp_path):
    (tmp_path/'run.json').write_text(json.dumps(dict(schema='rvw.sec-run/1', name='core', adapter=['../run.sh'],
                                                     config='c1', run_args=['--seed', 1], platform='../p.json')))
    b = run_adapter.load(tmp_path/'run.json')
    assert b['adapter'][0] == str((tmp_path/'../run.sh').resolve()) and b['_dir'] == tmp_path.resolve()
    argv = run_adapter.run_argv(b, 'x.elf', 'out')
    assert argv[1:] == ['run', '--elf', 'x.elf', '--out', 'out', '--rvfi-trace', '--probes', '--json',
                        '--config', 'c1', '--seed', '1']
    (tmp_path/'bad.json').write_text(json.dumps(dict(schema='rvw.sec-run/1', adapter='run.sh', platform='p')))
    with pytest.raises(ValueError, match='adapter argv'):
        run_adapter.load(tmp_path/'bad.json')


def run_folder(tmp_path):
    rows = [dict(schema='rvw.rvfi/1')] + [
        dict(order=i, cycle=c, pc=hex(0x80000000+4*i), insn='0x13', mode=3, mem_addr='0x0', mem_rmask=0, mem_wmask=0)
        for i, c in enumerate((10, 12, 20))]
    rows[-1].update(mem_addr='0x80001000', mem_wmask=15, insn='0x62a023')
    (tmp_path/'rvfi.jsonl').write_text('\n'.join(json.dumps(r) for r in rows)+'\n')
    probes = [dict(id=0, kind='cache', name='dcache_refill', fields=[['address', 32], ['data', 32]]),
              dict(id=1, kind='counter', name='refills', fields=[['inc', 8]])]
    lines = [dict(schema='rvw.probe-events/1', identity={}, probes=probes), [11, 0, 0x80001040, 5], [11, 1, 1],
             {'end': True, 'cycles': 30, 'counters': {'refills': 1}, 'events': {}}]
    (tmp_path/'probe-events.jsonl').write_text('\n'.join(json.dumps(x) for x in lines)+'\n')


def test_observations_from_a_c1_run(tmp_path, monkeypatch):
    run_folder(tmp_path)
    class E:  # the ELF only gives the tohost symbol
        symbols = {'tohost': 0x80001000}
    monkeypatch.setattr(run_adapter, 'Elf', lambda path: E)
    result = run_adapter.result_from_run(tmp_path, 'x.elf')
    obs = run_adapter.observe(result, ['cycles', 'retire_cycles', 'cache_events', 'probe_counters'])
    assert obs == dict(cycles=20, retire_cycles=[2, 8], probe_counters={'refills': 1},
                       cache_events=[dict(cycle=11, kind='cache', name='dcache_refill', address=0x80001040)])
    with pytest.raises(ValueError, match='bus trace'):
        run_adapter.observe(result, ['dbus_trace'])


def test_spec_receiver_loads_every_secret_line():
    assert spec_suite.receiver([{'x7': 1024}, {'x7': 64}]) == ['lw t5, 64(s1)', 'lw t5, 1024(s1)']


def test_trace_is_cut_at_the_tohost_store(tmp_path):
    run_folder(tmp_path)
    lines = (tmp_path/'rvfi.jsonl').read_text().splitlines()
    extra = dict(order=3, cycle=25, pc='0x8000000c', insn='0x6f', mode=3, mem_addr='0x0', mem_rmask=0, mem_wmask=0)
    end = dict(event='end', cycle=26, status='pass')
    (tmp_path/'rvfi.jsonl').write_text('\n'.join(lines + [json.dumps(extra), json.dumps(end)])+'\n')
    run_adapter.cut_trace(tmp_path/'rvfi.jsonl', tmp_path/'cut.jsonl', 0x80001000)
    cut = [json.loads(x) for x in (tmp_path/'cut.jsonl').read_text().splitlines()]
    assert [r.get('pc') for r in cut[1:-1]] == ['0x80000000', '0x80000004', '0x80000008']
    assert cut[-1] == end
