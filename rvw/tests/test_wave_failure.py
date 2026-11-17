from types import SimpleNamespace
import json
import pytest
from rvw.wave import failure

pytestmark = pytest.mark.fast


def test_binding(tmp_path):
    p = tmp_path / 'binding.toml'
    p.write_text('[riscv_formal.ports]\nrd_wdata="io_rd"\n')
    assert failure.binding_ports(p)['rd_wdata'] == 'io_rd'
    p = tmp_path / 'binding.json'
    p.write_text(json.dumps({'schema':'wrong','ports':{}}))
    with pytest.raises(ValueError):
        failure.binding_ports(p)


def setup(monkeypatch, wave, gcd_db, tmp_path):
    run = SimpleNamespace(artifact=lambda name: wave if name == 'wave' else None,
                          get=lambda name, default=None: {'details': {'wave_time_per_cycle': 10,
                            'wave_time_of_cycle_1': 5}, 'core':'test'}.get(name, default))
    monkeypatch.setattr(failure, 'open_run', lambda p: run)
    mismatch = {'cycle':2, 'order':1, 'actual':{'rd_wdata':'0x4'},
                'differences':{'rd_wdata':{'actual':'0x4','expected':'0x5'}}}
    monkeypatch.setattr(failure, 'compare', lambda *a: {'status':'mismatch', 'mismatch':mismatch})
    binding = tmp_path / 'binding.toml'
    binding.write_text('[riscv_formal.ports]\nrd_wdata="x"\n')
    return dict(run_dir='unused', db=str(gcd_db), binding=str(binding), out=str(tmp_path/'out'))


# Use the real database/wave driver walk, with only the Spike input seam replaced.
from test_wave_why import wave  # noqa: F401


def test_fallback(monkeypatch, wave, gcd_db, tmp_path):
    args = setup(monkeypatch, wave, gcd_db, tmp_path)
    monkeypatch.setattr(failure.Session, 'trace', lambda *a: {'status':'inconclusive','cause':'no engine'})
    r = failure.explain_run(**args, rerun=False)
    assert r['status'] == 'explained'
    assert r['time'] == 15
    assert r['chains'][0]['driver_walk']['trace']['value'] == '0x4'
    assert 'inferred' in r['chains'][0]['accuracy']


def test_no_mismatch(monkeypatch, wave, gcd_db, tmp_path):
    args = setup(monkeypatch, wave, gcd_db, tmp_path)
    monkeypatch.setattr(failure, 'compare', lambda *a: {'status':'inconclusive'})
    assert failure.explain_run(**args)['status'] == 'inconclusive'


def test_replay_must_reproduce(monkeypatch, wave, gcd_db, tmp_path):
    args = setup(monkeypatch, wave, gcd_db, tmp_path)
    monkeypatch.setattr(failure, 'covers', lambda *a: (False,'no wave'))
    monkeypatch.setattr(failure.adapter, 'parse_replay', lambda *a: SimpleNamespace(set=lambda **kw: kw))
    monkeypatch.setattr(failure.adapter, 'execute', lambda *a, **kw: SimpleNamespace(run=object()))
    old = failure.compare
    count = []
    def compare(*a):
        count.append(1)
        return old(*a) if len(count) == 1 else {'status':'match'}
    monkeypatch.setattr(failure, 'compare', compare)
    assert failure.explain_run(**args)['cause'] == 'replay did not reproduce the same mismatch'


def test_walk_control_edges(gcd_db, wave):
    from rvw.wave.why import why
    r = why(str(gcd_db), wave, 'x', 18, depth=1, include_control=True)
    assert any(c['dependency_kind'] == 'cond' for c in r['trace']['children'])


def test_exact_decimal_clock_metadata():
    from rvw.bundle.clock import wave_clock
    run = SimpleNamespace(get=lambda key: {'wave_time_per_cycle': '10', 'wave_time_of_cycle_1': '187'})
    clock = wave_clock(run, {})
    assert clock.known and clock.time(35) == 527


def test_project_comparison_does_not_also_select_a_bundled_core(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(failure, 'calculate', lambda args: (seen.append(args) or {'status':'match'}, 0))
    run = SimpleNamespace(artifact=lambda name: tmp_path/'rvfi.jsonl', dir=tmp_path,
                          get=lambda name: {'elf':'test.elf','core':'private-core'}[name])
    assert failure.compare(run, 'private/rvw.toml', None, 120)['status'] == 'match'
    assert seen[0].project == 'private/rvw.toml' and seen[0].core is None


def test_comparison_without_project_keeps_bundled_core(monkeypatch, tmp_path):
    seen = []
    monkeypatch.setattr(failure, 'calculate', lambda args: (seen.append(args) or {'status':'match'}, 0))
    run = SimpleNamespace(artifact=lambda name: tmp_path/'rvfi.jsonl', dir=tmp_path,
                          get=lambda name: {'elf':'test.elf','core':'boom'}[name])
    assert failure.compare(run, None, None, 120)['status'] == 'match'
    assert seen[0].project is None and seen[0].core == 'boom'
