import json
from pathlib import Path
import runpy
import pytest
pytestmark = pytest.mark.fast
ROOT = Path(__file__).resolve().parents[2]
ci = runpy.run_path(str(ROOT / 'scripts/ci-tiers.py'))


def test_tier_tools_are_inventory_names():
    names = {t['name'] for t in json.loads((ROOT / 'rvw/src/rvw/doctor/tools.json').read_text())['tools']}
    assert set(ci['TIERS']) == {'fast', 'native-light', 'examples', 'nightly'}
    for data in ci['TIERS'].values():
        assert set(data['tools']) <= names
    assert ci['TIERS']['fast']['tools'] == []
    assert ci['TIERS']['native-light']['seconds'] <= 120


def test_all_primary_scala_projects_have_suites():
    for path in ci['SCALA']:
        assert (ROOT / path / 'build.sbt').is_file()
    assert {'SpinalProbes', 'SpinalSoc', 'RiscvSim'} <= set(ci['SCALA'])
    assert all('compile' not in cmd for _, _, args in ci['commands']('nightly', 'scala') for cmd in args)


def test_nightly_python_does_not_select_fast_tests():
    plugin = (ROOT / 'scripts/ci_plugin.py').read_text()
    assert 'get_closest_marker("slow")' in plugin or "get_closest_marker('slow')" in plugin
    assert 'sha256(item.nodeid.encode())' in plugin
    assert 'CI inventory missing:' in plugin
