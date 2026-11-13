import copy
import json
from pathlib import Path
import pytest
from rvw.privilege import campaign, cofpmf

pytestmark = pytest.mark.fast


def config():
    return campaign.load('examples/privilege/sscofpmf.json')


def test_visibility_and_interrupt_matrix():
    rows = campaign.scenarios(config())
    assert len(rows) == len({r['id'] for r in rows}) == 12
    byid = {r['id']: r['assembly'] for r in rows}
    for mode in ('m', 's'):
        for local, glob in ((0, 1), (1, 0), (1, 1)):
            code = byid[f'sscofpmf-delivery-{mode}-{local}-{glob}']
            assert f'csrr t0, {mode}cause' in code
            assert f'csrc {mode}ip, t0' in code
            assert '9223372036854775821' in code
            assert f'li t0, {int(local and glob)}\n bne s0, t0, fail' in code
    # Latest pinned text makes M-mode visibility independent of mcounteren.
    assert 'li t0, 8\n bne t0, t1, fail' in byid['sscofpmf-scountovf-m-0']
    assert 'li t0, 0\n bne t0, t1, fail' in byid['sscofpmf-scountovf-s-0']
    assert 'la t1, access_site' in byid['sscofpmf-scountovf-u-1']


def test_overflow_rearm_model():
    c = cofpmf.Counter()
    c.write(-1)
    assert not c.overflow and not c.pending
    c.increment()
    assert c.value == 0 and c.overflow and c.pending
    c.pending = False
    c.write(-1)
    c.increment()
    assert c.overflow and not c.pending
    c.overflow = False
    c.write(-1)
    c.increment()
    assert c.pending
    c = cofpmf.Counter(inhibited=True)
    c.write(-1)
    c.increment()
    assert c.value == (1 << 64) - 1 and not c.pending


def test_project_events_never_claim_spike_support():
    c = config()
    c['cofpmf'].update(event_selector=7, counter_bits=64)
    rows = campaign.scenarios(c)
    hw = [r for r in rows if r.get('hardware_event')]
    assert len(hw) == 3
    assert all(r['reference_unavailable'] for r in hw)
    assert all('count_window:' in r['assembly'] for r in hw)
    assert all('csrw 0xb03' in r['assembly'] for r in hw)
    assert all(r['hardware_event']['event_selector'] == 7 for r in hw)


@pytest.mark.parametrize('field,value', [('counter',2), ('counter',32), ('counter',True),
    ('event_selector',0), ('event_selector',1 << 56), ('poll_iterations',0)])
def test_bad_project_options(field, value):
    c = config(); c['cofpmf'][field] = value
    with pytest.raises(ValueError):
        campaign.scenarios(c)


def test_unpinned_or_wrong_width():
    for field, value in [('spec_version','latest'), ('isa','rv32ima_sscofpmf_zihpm')]:
        c = config(); c[field] = value
        with pytest.raises(ValueError):campaign.scenarios(c)
    c = config(); c['cofpmf']['event_selector'] = 7
    with pytest.raises(ValueError, match='counter_bits'):campaign.scenarios(c)


def test_reference_does_not_execute_hardware_rows(tmp_path, monkeypatch):
    c = config(); c['cofpmf'].update(event_selector=7,counter_bits=64)
    rows = [r for r in campaign.scenarios(c) if r.get('hardware_event')]
    for r in rows:
        r.pop('assembly'); r['elf'] = r['id'] + '.elf'
        (tmp_path / r['elf']).write_bytes(b'fixture')
        r['elf_sha256'] = campaign.digest(tmp_path / r['elf'])
    (tmp_path / 'manifest.json').write_text(json.dumps(dict(schema='rvw.privilege-build/1',config=c,scenarios=rows)))
    monkeypatch.setattr(campaign.shutil,'which',lambda _: __file__)
    monkeypatch.setattr(campaign,'run_group',lambda *a,**k: pytest.fail('unsupported event executed'))
    r = campaign.reference(tmp_path)
    assert r['status'] == 'inconclusive'
    assert all(s['status'] == 'inconclusive' for s in r['scenarios'])


def test_planner_catalogue():
    rows = json.loads(Path('rvw/src/rvw/regress/suite_requirements.json').read_text())
    r = next(r for r in rows if r['name'] == 'sscofpmf')
    assert {'xlen:64','ext:sscofpmf','ext:zihpm'} <= set(r['requires'])
