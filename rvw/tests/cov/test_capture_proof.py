"""C8 proof capture regressions at guard and publication boundaries."""
import hashlib
import json
from pathlib import Path
import shutil

import pytest
from race_injection import race_injector
from rvw.cov import proof
from .test_proof import _setup, TINY, needs_sby


@needs_sby
@pytest.mark.parametrize('revert', [False, True])
def test_proof_database_identity_is_the_parsed_capture(tmp_path, race_injector, revert):
    dut, harness = TINY.split('module h')
    cfg, db = _setup(tmp_path, 'module h' + harness, "s == 2'd3", dut=dut, extra={'reset': None})
    original = db.read_bytes()
    obj = json.loads(original)
    obj['point_universe'] = 'changed'
    edit = race_injector.file(proof, 'elaborate', db, json.dumps(obj).encode(), replace=True, revert=revert)
    result = proof.prove(cfg, db, tmp_path / 'proof')
    assert edit.fired
    assert result['point_universe'] == 'u'
    assert result['database_sha256'] == hashlib.sha256(original).hexdigest()
    assert result['database_sha256'] == result['inputs'][str(db)]


@needs_sby
@pytest.mark.parametrize('replace', [False, True])
def test_proof_refuses_tool_edit_and_revert(tmp_path, monkeypatch, race_injector, replace):
    tool = shutil.which('yosys')
    directory = tmp_path / 'bin'
    directory.mkdir()
    wrapper = directory / 'yosys'
    wrapper.write_text(f'#!/bin/sh\nexec "{tool}" "$@"\n')
    wrapper.chmod(0o755)
    import os
    monkeypatch.setenv('PATH', str(directory) + os.pathsep + os.environ['PATH'])
    dut, harness = TINY.split('module h')
    cfg, db = _setup(tmp_path, 'module h' + harness, "s == 2'd3", dut=dut, extra={'reset': None})
    edit = race_injector.file(proof, 'elaborate', wrapper, wrapper.read_bytes() + b'# edited\n',
                              replace=replace, revert=True)
    with pytest.raises(ValueError, match='input_not_captured:tool'):
        proof.prove(cfg, db, tmp_path / 'proof')
    assert edit.fired
    assert not (tmp_path / 'proof/exclusions.json').exists()
