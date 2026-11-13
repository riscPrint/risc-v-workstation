"""Fast campaign checks. Native smoke runs are separate."""
import json
from pathlib import Path
from types import SimpleNamespace
import pytest
from rvw.privilege import campaign
from rvw.privilege.programs import controls, control_program
from rvw.privilege.cli import execute


def test_control_matrix():
    rows = controls({})
    assert len(rows) == 30
    assert len({r['id'] for r in rows}) == 30
    for r in rows:
        text = r['assembly']
        assert 'retry_trap:' in text and 'bne t0, t1, fail' in text
        if r['instruction'] == 'wfi':
            assert 'csrw mideleg, t0' in text
        assert 'li t1, 2\n' in text if r['mode'] == 'U' or (r['mode'] == 'S' and r['enabled']) else 'done:' in text


@pytest.mark.parametrize('value', [[], ['S', 'S'], ['H']])
def test_bad_modes(tmp_path, value):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(dict(schema='rvw.privilege/1', modes=value)))
    with pytest.raises(ValueError):
        campaign.load(path)


def test_missing_supervisor(tmp_path):
    path = tmp_path / 'config.json'
    path.write_text(json.dumps(dict(schema='rvw.privilege/1', priv='mu')))
    with pytest.raises(ValueError, match='supervisor support'):
        campaign.load(path)


def make_build(tmp_path):
    elf = tmp_path / 'one.elf'
    elf.write_bytes(b'elf')
    manifest = dict(schema='rvw.privilege-build/1', config={}, scenarios=[
        dict(id='one', elf=elf.name, elf_sha256=campaign.digest(elf), bins=['control.test'])])
    (tmp_path / 'manifest.json').write_text(json.dumps(manifest))
    return elf


def test_reference_timeout_is_not_pass(tmp_path, monkeypatch):
    make_build(tmp_path)
    monkeypatch.setattr(campaign.shutil, 'which', lambda _: str(tmp_path / 'one.elf'))
    monkeypatch.setattr(campaign, 'run_group', lambda *a, **k: SimpleNamespace(timed_out=True, returncode=0, stderr=''))
    assert campaign.reference(tmp_path)['status'] == 'inconclusive'


def test_changed_elf_rejected(tmp_path, monkeypatch):
    elf = make_build(tmp_path)
    monkeypatch.setattr(campaign.shutil, 'which', lambda _: str(elf))
    elf.write_bytes(b'changed')
    with pytest.raises(ValueError, match='ELF changed'):
        campaign.reference(tmp_path)


def test_no_c1_cannot_earn_group(tmp_path):
    make_build(tmp_path)
    result = campaign.check(tmp_path, tmp_path / 'missing', tmp_path / 'platform.json')
    assert result['status'] == 'inconclusive'
    assert result['counts']['pass'] == 0
    assert result['groups'] == {'control.test': 'inconclusive'}


@pytest.mark.parametrize('value', [0, -1, float('nan'), float('inf')])
def test_invalid_timeout(value):
    with pytest.raises(ValueError, match='timeout'):
        execute('reference', directory='missing', timeout=value)


@pytest.mark.parametrize('comparison,expected', [
    ({'status': 'match', 'trace_complete': True, 'end_status': 'pass', 'instructions': 10, 'synchronized': 0}, 'pass'),
    ({'status': 'match', 'trace_complete': False, 'end_status': 'pass', 'instructions': 10, 'synchronized': 0}, 'inconclusive'),
    ({'status': 'match', 'trace_complete': True, 'end_status': 'pass', 'instructions': 10, 'synchronized': 1}, 'inconclusive'),
    ({'status': 'mismatch'}, 'fail'),
])
def test_c1_strict_evidence(tmp_path, monkeypatch, comparison, expected):
    import rvw.results
    elf = make_build(tmp_path)
    result = tmp_path / 'result.json'
    result.write_text('{}')
    (tmp_path / 'trace.jsonl').write_text('trace')
    run = SimpleNamespace(elf_sha256=campaign.digest(elf), path=tmp_path, why_inconclusive=None,
                          status='pass', artifacts={'rvfi_trace': 'trace.jsonl'})
    monkeypatch.setattr(rvw.results, 'load_run', lambda _: run)
    monkeypatch.setattr(campaign, 'run_group', lambda *a, **k:
        SimpleNamespace(timed_out=False, returncode=0, stdout=json.dumps(comparison)))
    checked = campaign.check(tmp_path, tmp_path, 'platform.json')
    assert checked['status'] == expected
    assert checked['groups'] == {'control.test': expected}


def test_wfi_programs():
    from rvw.privilege.wake import programs
    config = {'timer': {'mtime': 0x200bff8, 'mtimecmp': 0x2004000, 'msip': 0x2000000, 'delta': 100}}
    rows = programs(config)
    assert len(rows) == 4
    assert len({r['id'] for r in rows}) == 4
    for row in rows:
        text = row['assembly']
        assert ' wfi\n' in text
        assert 'bne s0, t0, fail' in text
        assert 'bltu t0, t1, fail' in text and 'bgeu t0, t1, fail' in text
        assert 'j wait_pending' in text if row['enabled'] else 'j check_state' in text


@pytest.mark.parametrize('timer', [{}, {'mtime': 1, 'mtimecmp': 8, 'msip': 16, 'delta': 100},
                                  {'mtime': 0, 'mtimecmp': 8, 'msip': 16, 'delta': 0}])
def test_wfi_bad_config(timer):
    from rvw.privilege.wake import programs
    with pytest.raises(ValueError):
        programs({'timer': timer})
