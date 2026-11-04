import json
from types import SimpleNamespace

import pytest
from rvw.cli import main
from rvw.doctor import backends
from rvw.doctor.conformance import artifacts


def test_gui_missing_and_failed_version(monkeypatch):
    monkeypatch.setattr(backends.shutil, 'which', lambda name: None)
    assert backends.probe('waves')['status'] == 'error'
    monkeypatch.setattr(backends.shutil, 'which', lambda name: '/synthetic/' + name)
    monkeypatch.setattr(backends, 'run_group', lambda *a, **kw: SimpleNamespace(returncode=1, stdout='', stderr='bad'))
    assert backends.probe('ide')['status'] == 'error'


@pytest.mark.parametrize('extensions,ready', [('riscprint.risc-v-workstation@0.1.0', True), ('other.extension@1', False)])
def test_ide_requires_workstation_extension(monkeypatch, extensions, ready):
    monkeypatch.setattr(backends.shutil, 'which', lambda name: '/synthetic/' + name)
    monkeypatch.setattr(backends, 'run_group', lambda cmd, **kw: SimpleNamespace(
        returncode=0, stdout=extensions if '--list-extensions' in cmd else '1.100.0', stderr=''))
    assert (backends.probe('ide')['status'] == 'ready') is ready


@pytest.mark.parametrize('args', [
    ['--smoke-options', 'wave'], ['--smoke-elf', 'elf', '--smoke-options', 'bad'],
    ['--smoke-elf', 'elf', '--smoke-platform', 'platform'], ['--install', 'ide'],
])
def test_invalid_smoke_and_install_options(args, capsys):
    assert main(['doctor', *args, '--json']) == 2
    assert json.loads(capsys.readouterr().out)['status'] == 'error'


@pytest.mark.parametrize('name', [None, '/absolute/path', '../outside', 'missing', 'empty'])
def test_requested_artifact_must_exist_inside_run(tmp_path, name):
    (tmp_path / 'empty').touch()
    result = artifacts({'artifacts': {'wave': name}}, tmp_path, ['wave'], {},
                       elf='elf', core='test', config='default')
    assert result[0]['status'] == 'error'


def trace_file(tmp_path, *, end='pass', config='default', malformed=False):
    from rvw.cosim.trace import HEX, INT, BOOL
    header = dict(schema='rvw.rvfi/1', xlen=32, isa='rv32im', core='test', config=config, elf='elf')
    row = {k: '0x0' for k in HEX}
    row.update({k: 0 for k in INT})
    row.update({k: False for k in BOOL})
    row.update(mode=3, insn='0x13')
    rows = [header, row]
    if end is not None:
        rows.append(dict(event='end', cycle=1, status=end))
    path = tmp_path / 'rvfi.jsonl'
    path.write_text('\n'.join(json.dumps(x) for x in rows) + ('\nbad' if malformed else '\n'))
    return path


@pytest.mark.parametrize('end,config,malformed,ready', [
    ('pass', 'default', False, True), (None, 'default', False, False),
    ('fail', 'default', False, False), ('pass', 'other', False, False),
    ('pass', 'default', True, False),
])
def test_c2_requires_complete_bound_trace(tmp_path, end, config, malformed, ready):
    trace_file(tmp_path, end=end, config=config, malformed=malformed)
    checks = artifacts(dict(status='pass', artifacts={'rvfi_trace': 'rvfi.jsonl'}), tmp_path, ['rvfi'],
                       dict(xlen=32, isa={'default': 'rv32im'}), elf='elf', core='test', config='default')
    schema = next(c for c in checks if c['name'] == 'adapter.c2')
    assert (schema['status'] == 'ready') is ready
    assert not any(c['name'] == 'adapter.c2_mapping' and c['status'] == 'ready' for c in checks)


@pytest.mark.parametrize('comparison,ready', [
    (dict(status='match', trace_complete=True, end_status='pass'), True),
    (dict(status='match', trace_complete=False, end_status=None), False),
    (dict(status='match', trace_complete=True, end_status='fail'), False),
    (dict(status='mismatch', trace_complete=True, end_status='pass'), False),
])
def test_c2_reference_match_needs_complete_pass(tmp_path, monkeypatch, comparison, ready):
    import rvw.cosim.cli
    trace_file(tmp_path)
    monkeypatch.setattr(rvw.cosim.cli, 'execute_json', lambda *a, **kw: comparison)
    checks = artifacts(dict(status='pass', artifacts={'rvfi_trace': 'rvfi.jsonl'}), tmp_path, ['rvfi'],
                       dict(xlen=32, isa={'default': 'rv32im'}), elf='elf', core='test', config='default', platform='platform')
    result = next(c for c in checks if c['name'] == 'adapter.c2_mapping')
    assert (result['status'] == 'ready') is ready
