"""Validate workflow wiring without starting a workflow or native tool."""
import ast
import json
from pathlib import Path
import re
import runpy

import pytest
import yaml

pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize('name', ['ci.yml', 'nightly.yml', 'conventional.yml'])
def test_workflow_yaml_and_scripts(name):
    text = (ROOT / '.github/workflows' / name).read_text()
    data = yaml.load(text, Loader=yaml.BaseLoader)
    assert data['jobs']
    for key, job in data['jobs'].items():
        if job['runs-on'] == 'ubuntu-latest':
            assert job['if'] == "vars.RVW_LINUX_CI == 'enabled'"
        else:
            assert job['runs-on'] == ['self-hosted', 'macOS', 'ARM64', 'rvw-local']
        assert any(step.get('if') == 'always()' for step in job['steps']), key
    for path in re.findall(r'\bscripts/[a-zA-Z0-9_/-]+\.(?:py|sh)', text):
        assert (ROOT / path).is_file(), path


def test_native_markers_use_real_inventory_names():
    names = {t['name'] for t in json.loads((ROOT / 'rvw/src/rvw/doctor/tools.json').read_text())['tools']}
    tree = ast.parse((ROOT / 'rvw/tests/ci_native/test_tools.py').read_text())
    marked = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == 'needs':
            tools = {ast.literal_eval(arg) for arg in node.args}
            assert tools and tools <= names
            marked.append(tools)
    assert len(marked) == 4
    assert 'native_light' in (ROOT / 'rvw/pyproject.toml').read_text()
    assert (ROOT / 'scripts/ci_plugin.py').is_file()


def test_every_tier_command_points_to_a_real_directory():
    ci = runpy.run_path(str(ROOT / 'scripts/ci-tiers.py'))
    for component in ('python', 'scala', 'rust', 'javascript', 'components', 'vip'):
        for _, cwd, command in ci['commands']('nightly', component):
            assert cwd.is_dir()
            assert command


def test_scala_matrix_matches_the_tier():
    ci = runpy.run_path(str(ROOT / 'scripts/ci-tiers.py'))
    workflow = yaml.load((ROOT / '.github/workflows/nightly.yml').read_text(), Loader=yaml.BaseLoader)
    assert set(workflow['jobs']['scala']['strategy']['matrix']['part']) == set(ci['SCALA'])


def test_required_fast_job_fails_if_path_selection_fails():
    data = yaml.load((ROOT / '.github/workflows/ci.yml').read_text(), Loader=yaml.BaseLoader)
    assert data['jobs']['fast']['if'] == 'always()'
    assert any('test "$SELECTION_STATUS" = success' in step.get('run', '') for step in data['jobs']['fast']['steps'])
