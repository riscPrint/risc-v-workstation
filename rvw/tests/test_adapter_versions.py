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
