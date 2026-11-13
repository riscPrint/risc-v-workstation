import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from rvw.cli import main
from rvw.common.project import load_project
from rvw.doctor import check
from rvw.mcp.registry import discover

pytestmark = pytest.mark.fast


def test_records_keep_version_warnings():
    records = check.native_records('WARNING Verilator 5.049: outside tested version table (5.052)\nPRESENT Verilator: 5.049\nMISSING JDK\n')
    assert [r['status'] for r in records] == ['warning', 'ready', 'error']
    assert records[1]['version'] == '5.049'
    assert all(r['qualification'] == 'version_probe_only' for r in records)


def test_diagnostics_do_not_install(tmp_path, monkeypatch):
    calls = []
    def run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=1, stdout='MISSING uv\n', stderr='')
    monkeypatch.setattr(check, 'run_group', run)
    report = check.diagnose(project=tmp_path)
    assert report['exit_code'] == 1
    assert all('--check' in cmd for cmd in calls)
    assert any(c['name'] == 'project' and c['status'] == 'error' for c in report['checks'])
    assert any(b['status'] == 'skipped' for b in report['backends'])


def test_explicit_install_flags(tmp_path, monkeypatch):
    calls = []
    def run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout='plan', stderr='')
    monkeypatch.setattr(check, 'run_group', run)
    report = check.diagnose(project=tmp_path, install='formal', dry_run=True, yes=True)
    assert '--with-formal' in calls[0] and '--dry-run' in calls[0] and '--yes' in calls[0]
    assert '--check' in calls[1]
    assert report['exit_code'] != 0
    assert report['installation']['dry_run']


@pytest.mark.parametrize('options', [{'features': 'bad'}, {'yes': True}, {'dry_run': True}, {'install': 'bad'}])
def test_bad_options(options):
    assert check.diagnose(**options)['exit_code'] == 2


def test_cli_json(capsys):
    assert main(['doctor', '--features', 'bad', '--json']) == 2
    assert json.loads(capsys.readouterr().out)['schema'] == 'rvw.doctor/1'


def test_diagnostic_mcp_stays_read_only_and_smoke_is_explicit():
    tools, problems = discover({'doctor'})
    assert not problems
    tools = {tool.name: tool for tool in tools}
    assert set(tools) == {'rvw_doctor', 'doctor_smoke'}
    tool = tools['rvw_doctor']
    assert 'smoke_elf' not in tool.input_schema['properties']
    assert 'elf' not in tool.input_schema['properties']
    assert tools['doctor_smoke'].long
    assert not tools['doctor_smoke'].annotations.get('readOnlyHint', False)
    assert 'install' not in tool.input_schema['properties']
    assert tool.annotations['readOnlyHint']


def test_version_pin(tmp_path):
    path = tmp_path / 'rvw.toml'
    path.write_text('[project]\nrvw_version = "99"\n[core]\nname = "test"\n')
    with pytest.raises(ValueError, match='needs rvw'):
        load_project(path)


def test_machine_version_policy():
    records = check.native_records('PRESENT Verilator: 5.049\nWRONG VERSION JDK: 25 (need 21)\n', {'Verilator': '5.052', 'JDK': '21.0.13'})
    assert records[0]['installed'] and records[0]['support'] == 'usable'
    assert records[0]['tested_table_match'] is False
    assert records[1]['support'] == 'unsupported'


@pytest.mark.parametrize('smoke_flags', ['', 'wave,coverage'])
@pytest.mark.parametrize('change,ready', [
    ({}, True), ({'elf_sha256': 'b' * 64}, False),
    ({'seed': 2}, False), ({'max_cycles': 20000}, False),
    ({'synthesized': True}, False), ({'wall_clock_timeout': True}, False),
])
def test_smoke_requires_requested_identity_and_conclusive_result(tmp_path, monkeypatch, change, ready, smoke_flags):
    import hashlib
    elf = tmp_path / 'smoke.elf'
    elf.write_bytes(b'\x7fELFfixture')
    cfg = SimpleNamespace(adapter=['fixture'], path=tmp_path / 'rvw.toml', name='fixture',
                          configs=['default'], default_config='default', build_timeout_s=10,
                          suites={}, input_complete=False, identity=False, identity_capture=False,
                          source_repo=tmp_path)
    monkeypatch.setattr(check, 'load_project', lambda p: SimpleNamespace(path=cfg.path, root=tmp_path, get=lambda *keys: None))
    monkeypatch.setattr(check, 'load_config', lambda **kw: cfg)
    def run(cmd, **kwargs):
        if 'info' in cmd:
            info = dict(schema='rvw.adapter/1', core='fixture', configs=['default'],
                        default_config='default', xlen=32, isa={'default': 'rv32im'})
            return SimpleNamespace(returncode=0, stdout=json.dumps(info), stderr='')
        if 'run' in cmd:
            record = dict(schema='rvw.run/1', core='fixture', config='default', status='pass',
                          seed=1, max_cycles=10000, elf=str(elf), cycles=10, instret=1,
                          elf_sha256=hashlib.sha256(elf.read_bytes()).hexdigest())
            if smoke_flags:
                assert '--wave' in cmd and '--coverage' in cmd
                record['artifacts'] = {'wave': 'wave.vcd', 'coverage': 'coverage.dat'}
                for artifact in record['artifacts'].values():
                    (Path(cmd[cmd.index('--out') + 1]) / artifact).write_text('fixture')
            record.update(change)
            (Path(cmd[cmd.index('--out') + 1]) / 'result.json').write_text(json.dumps(record))
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(check, 'run_group', run)
    result = check.diagnose(project=tmp_path, smoke_elf=elf, smoke_flags=smoke_flags)
    smoke = next(c for c in result['checks'] if c['name'] == 'adapter.build_run')
    assert (smoke['status'] == 'ready') is ready


def test_install_all_preserves_native_installer_scope(tmp_path, monkeypatch):
    calls = []
    def run(cmd, **kwargs):
        calls.append(cmd)
        return SimpleNamespace(returncode=0, stdout='', stderr='')
    monkeypatch.setattr(check, 'run_group', run)
    result = check.diagnose(project=tmp_path, install='all', dry_run=True)
    assert result['installation']['exit_code'] == 0
    assert '--with-cosim' in calls[0] and '--with-gem5' in calls[0]
    assert '--with-ide' not in calls[0] and '--with-waves' not in calls[0]


def test_info_waits_for_the_project_startup_time(tmp_path, monkeypatch):
    cfg = SimpleNamespace(adapter=['fixture'], path=tmp_path / 'rvw.toml', name='fixture', configs=['default'],
                          default_config='default', startup_s=300.0, build_timeout_s=10, suites={},
                          input_complete=False, identity=False, identity_capture=False, source_repo=tmp_path)
    monkeypatch.setattr(check, 'load_project', lambda p: SimpleNamespace(path=cfg.path, root=tmp_path, get=lambda *keys: None))
    monkeypatch.setattr(check, 'load_config', lambda **kw: cfg)
    seen = {}
    def run(cmd, **kwargs):
        if 'info' in cmd:
            seen['timeout'] = kwargs['timeout']
            return SimpleNamespace(returncode=-9, stdout='', stderr='', timed_out=True)
        return SimpleNamespace(returncode=1, stdout='', stderr='')
    monkeypatch.setattr(check, 'run_group', run)
    report = check.diagnose(project=tmp_path)
    info = next(c for c in report['checks'] if c['name'] == 'adapter.info')
    assert seen['timeout'] == 300.0
    assert info['status'] == 'error' and 'core.startup_s' in info['detail']
