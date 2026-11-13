"""A debug profile file must name its target. The built-in model is never a silent default."""
import json
import subprocess
import sys

import pytest

pytestmark = pytest.mark.fast


def _suite(tmp_path, text, *extra):
    path = tmp_path / 'p.toml'
    path.write_text('schema = "rvw.debug-profile/1"\nname = "mycore"\nscratch = 0x80010000\n' + text)
    return subprocess.run([sys.executable, '-m', 'rvw', 'debug', 'suite', '--profile', str(path),
                           '--out', str(tmp_path / 'out'), '--group', 'dm', *extra],
                          capture_output=True, text=True, timeout=120)


def test_profile_without_transport_is_refused(tmp_path):
    run = _suite(tmp_path, '')
    assert run.returncode != 0, run.stdout
    assert 'transport' in (run.stdout + run.stderr)
    assert not (tmp_path / 'out' / 'results.json').exists()


def test_explicit_model_transport_still_runs_the_self_test(tmp_path):
    run = _suite(tmp_path, '[transport]\nkind = "model"\n')
    assert run.returncode == 0, run.stdout + run.stderr
    results = json.loads((tmp_path / 'out' / 'results.json').read_text())
    assert results['transport'] == 'model'
