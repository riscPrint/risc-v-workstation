"""Run bindings resolve data paths against the binding, including bare filenames."""
import json
import pytest
from rvw.sec import run_adapter

pytestmark = pytest.mark.fast


def test_bare_platform_filename_is_relative_to_binding(tmp_path):
    path = tmp_path / 'run.json'
    path.write_text(json.dumps({'schema': run_adapter.SCHEMA, 'adapter': ['python3'], 'platform': 'p.json'}))
    result = run_adapter.load(path)
    assert result['platform'] == str(tmp_path / 'p.json')
    assert result['adapter'] == ['python3']


def test_bare_adapter_file_is_relative_to_binding(tmp_path):
    (tmp_path / 'run.sh').write_text('#!/bin/sh\nexit 0\n')
    path = tmp_path / 'run.json'
    path.write_text(json.dumps({'schema': run_adapter.SCHEMA, 'adapter': ['run.sh'], 'platform': 'p.json'}))
    result = run_adapter.load(path)
    assert result['adapter'] == [str(tmp_path / 'run.sh')]
