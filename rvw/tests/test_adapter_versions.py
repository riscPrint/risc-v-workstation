import json
from pathlib import Path

import pytest

from rvw.runs.versions import resolve


def test_revision_marker_and_api_negotiation(tmp_path):
    script = tmp_path / 'adapter.sh'
    script.write_text('#!/bin/sh\nexit 0\n')
    (tmp_path / 'API').write_text('old\n')
    path = tmp_path / '.rvw-adapters.json'
    data = dict(schema='rvw.adapter-versions/1', marker='API', revisions={'newrev': 'new'},
        adapters={'old': dict(api=1, command=['adapter.sh', '--old']),
                  'new': dict(api=1, command=['adapter.sh', '--new'])})
    path.write_text(json.dumps(data))
    assert resolve(tmp_path, 'oldrev')[0][-1] == '--old'
    command, identity = resolve(tmp_path, 'newrev')
    assert command[-1] == '--new' and identity['version'] == 'new' and len(identity['executable_sha256']) == 64
    data['adapters']['new']['api'] = 2
    path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='unsupported adapter API'): resolve(tmp_path, 'newrev')
    data.pop('marker'); path.write_text(json.dumps(data))
    with pytest.raises(ValueError, match='unsupported revision'): resolve(tmp_path, 'missing')


def test_legacy_and_outside_captured_tree(tmp_path):
    assert resolve(tmp_path, 'rev') is None
    (tmp_path / '.rvw-adapters.json').write_text(json.dumps(dict(schema='rvw.adapter-versions/1',
        marker='../outside', adapters={})))
    with pytest.raises(ValueError, match='captured source'): resolve(tmp_path, 'rev')


def test_captured_launcher_records_selection_and_skips_unsupported(tmp_path):
    from rvw.runs.inputs import DebugInputs
    from rvw.runs.adapter import Command, execute
    inputs = DebugInputs()
    source = tmp_path / 'source'
    source.mkdir()
    script = source / 'adapter.sh'
    script.write_text('#!/bin/sh\nexit 0\n'); script.chmod(0o755)
    manifest = source / '.rvw-adapters.json'
    manifest.write_text(json.dumps(dict(schema='rvw.adapter-versions/1', revisions={'rev': 'v1'},
        adapters={'v1': dict(api=1, command=['adapter.sh'])})))
    captured = inputs.build_tree(source, git=False)
    command = Command(exe=['/must/not/run'])
    selected = inputs.launcher_command(command, captured, revision='rev')
    assert selected.exe[-1] == str(captured.copy / 'adapter.sh')
    assert Path(selected.exe[0]).is_file()
    identity = json.loads(selected.env['RVW_CAPTURE_SOURCE'])
    assert identity['adapter_selection']['version'] == 'v1'
    unsupported = inputs.launcher_command(command, captured, revision='unknown')
    attempt = execute(unsupported, tmp_path / 'out', lock=False)
    assert attempt.run is None and 'unsupported revision' in attempt.error
    assert attempt.returncode is None


def test_project_registry_supports_real_revisions_without_old_manifest(tmp_path):
    from rvw.runs.inputs import DebugInputs
    from rvw.runs.adapter import Command
    root=tmp_path/'project';root.mkdir()
    registry=root/'history';registry.mkdir()
    script=registry/'run.sh';script.write_text('#!/bin/sh\nexit 0\n');script.chmod(0o755)
    manifest=registry/'adapters.json'
    manifest.write_text(json.dumps(dict(schema='rvw.adapter-versions/1',revisions={'old':'legacy','new':'current'},
        adapters={name:dict(api=1,command=['run.sh','--era',name]) for name in ('legacy','current')})))
    config=root/'debug.toml'
    config.write_text('[core]\nadapter_versions="history/adapters.json"\n')
    source=tmp_path/'core';source.mkdir()
    (source/'rtl.v').write_text('module core;endmodule')
    inputs=DebugInputs();inputs.config('fixture',explicit=config)
    captured=inputs.build_tree(source,git=False)
    manifest.write_text('corrupt original after capture')
    selected=inputs.launcher_command(Command(exe=['/must/not/run']),captured,revision='old')
    identity=json.loads(selected.env['RVW_CAPTURE_SOURCE'])
    assert selected.exe[-2:]==['--era','legacy']
    assert identity['adapter_selection']['manifest_scope']=='project'
    descriptor=json.loads(Path(selected.env['RVW_CAPTURE_INPUTS']).read_text())
    assert any(row['path'].endswith('adapters.json') for row in descriptor['files'])
    unknown=inputs.launcher_command(Command(),captured,revision='unknown')
    assert 'unsupported revision' in unknown.env['RVW_ADAPTER_RESOLUTION_ERROR']


def test_project_registry_does_not_leak_to_next_core_config(tmp_path):
    from rvw.runs.inputs import DebugInputs
    inputs=DebugInputs()
    inputs.adapter_registry=tmp_path/'previous.json'
    inputs.adapter_registry_tree=object()
    config=tmp_path/'next.toml';config.write_text('[core]\nsource_env="NEXT"\n')
    inputs.config('next',explicit=config)
    assert inputs.adapter_registry is None and inputs.adapter_registry_tree is None
